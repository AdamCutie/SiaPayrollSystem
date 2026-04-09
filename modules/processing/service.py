import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from core.database import db
from integrations.hr.adapter import (
    get_synced_active_employees,
    get_synced_attendance_list,
    get_synced_approved_leave_dates,
    get_synced_employee_payroll_config,
    get_synced_overtime_requests,
    get_synced_undertime_records,
)
from modules.compensation.service import CompensationService
from db.models import PayrollSnapshot, Holiday
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

class PayrollProcessingService:
    """
    Orchestrates the payroll run and saves results to our new database.
    Includes duplicate prevention and detailed background logging.
    """

    @staticmethod
    def _count_weekdays(start_date: datetime, end_date: datetime) -> int:
        start_day = start_date.date()
        end_day = end_date.date()
        if end_day < start_day: return 0
        days = 0
        cursor = start_day
        while cursor <= end_day:
            if cursor.weekday() < 6: days += 1
            cursor += timedelta(days=1)
        return days

    @staticmethod
    def _validate_payroll_config(config) -> list[str]:
        issues: list[str] = []
        def check_positive(field: str, value: float):
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
                issues.append(f"{field} must be > 0")
        def check_non_negative(field: str, value: float):
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
                issues.append(f"{field} must be >= 0")
        check_positive("basicSalary", config.basicSalary)
        check_non_negative("housingAllowance", config.housingAllowance)
        check_non_negative("latePenaltyRate", config.latePenaltyRate)
        return issues

    @staticmethod
    def _parse_late_duration_to_hours(value, field_name: str = "") -> float:
        if value in (None, "", 0, 0.0, "0", "00:00", "00:00:00"): return 0.0
        if isinstance(value, (int, float)):
            numeric = float(value)
            if not math.isfinite(numeric) or numeric <= 0: return 0.0
            if "minute" in field_name.casefold(): return round(numeric / 60.0, 4)
            return round(numeric, 4)
        if isinstance(value, str):
            raw = value.strip()
            if not raw: return 0.0
            if ":" in raw:
                parts = raw.split(":")
                try:
                    h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
                    s = int(parts[2]) if len(parts) > 2 else 0
                    return round((h * 3600 + m * 60 + s) / 3600.0, 4)
                except: return 0.0
            try:
                numeric = float(raw)
                if numeric <= 0: return 0.0
                if "minute" in field_name.casefold(): return round(numeric / 60.0, 4)
                return round(numeric, 4)
            except: return 0.0
        return 0.0

    @classmethod
    def _calculate_hr_late_penalties(cls, attendance_logs: list[dict], late_penalty_rate: float) -> float:
        """Calculates late penalties by taking the maximum late duration per day."""
        daily_max_lates = {} # date_str -> max_late_hours
        
        for log in attendance_logs:
            raw_date = log.get("date")
            if not raw_date: continue
            
            # Normalize date to YYYY-MM-DD
            date_str = raw_date.split("T")[0] if isinstance(raw_date, str) else raw_date.date().isoformat()
            
            for field_name in ("lateTime", "lateHours", "lateMinutes", "late", "tardiness"):
                if field_name not in log: continue
                late_hours = cls._parse_late_duration_to_hours(log.get(field_name), field_name)
                if late_hours > 0:
                    current_max = daily_max_lates.get(date_str, 0.0)
                    daily_max_lates[date_str] = max(current_max, late_hours)
                    break
                    
        total_hours = sum(daily_max_lates.values())
        return round(total_hours * float(late_penalty_rate or 0), 2)

    @classmethod
    def _build_late_penalty_items(cls, attendance_logs: list[dict], late_penalty_rate: float) -> list[dict]:
        """Groups late penalty details by day, taking only the maximum for each."""
        daily_max_items = {} # date_str -> {late_hours, amount, raw_date}
        
        for log in attendance_logs:
            raw_date = log.get("date")
            if not raw_date: continue
            
            # Normalize date to YYYY-MM-DD
            date_str = raw_date.split("T")[0] if isinstance(raw_date, str) else raw_date.date().isoformat()
            
            for field_name in ("lateTime", "lateHours", "lateMinutes", "late", "tardiness"):
                if field_name not in log: continue
                late_hours = cls._parse_late_duration_to_hours(log.get(field_name), field_name)
                if late_hours <= 0: continue
                
                if date_str not in daily_max_items or late_hours > daily_max_items[date_str]["late_hours"]:
                    # Capture the raw value if it's already a time string, otherwise format it
                    raw_val = log.get(field_name)
                    late_time_str = raw_val if (isinstance(raw_val, str) and ":" in raw_val) else f"{int(late_hours)}:{int((late_hours*60)%60):02d}"
                    
                    daily_max_items[date_str] = {
                        "date": raw_date,
                        "late_hours": round(late_hours, 2),
                        "late_time": late_time_str,
                        "amount": round(late_hours * float(late_penalty_rate or 0), 2),
                    }
                break
                
        # Return items sorted by date
        return [daily_max_items[d] for d in sorted(daily_max_items.keys())]

    @classmethod
    async def _calculate_synced_overtime_pay(cls, employee_number: str, start_date: datetime, end_date: datetime, basic_salary: float) -> float:
        requests = await get_synced_overtime_requests(employee_number=employee_number, start_date=start_date, end_date=end_date)
        approved = [r for r in requests if str(r.get("status", "")).casefold() == "approved"]
        hourly_rate = ((float(basic_salary) / 26.0) / 8.0) * 1.25
        return round(sum(cls._parse_overtime_hours(r.get("overtimeWorked")) for r in approved) * hourly_rate, 2)

    @staticmethod
    def _parse_overtime_hours(value) -> float:
        if not value: return 0.0
        if isinstance(value, (int, float)): return float(value)
        if ":" in str(value):
            parts = str(value).split(":")
            return int(parts[0]) + int(parts[1])/60.0
        return float(value)

    @classmethod
    async def _calculate_synced_undertime_deduction(cls, employee_number: str, start_date: datetime, end_date: datetime, basic_salary: float) -> float:
        """Calculates undertime deductions by taking the maximum undertime hours per day."""
        records = await get_synced_undertime_records(employee_number=employee_number, start_date=start_date, end_date=end_date)
        
        daily_max_undertime = {} # date_str -> max_hours
        for r in records:
            raw_date = r.get("date")
            if not raw_date: continue
            
            # Normalize date
            date_str = raw_date.split("T")[0] if isinstance(raw_date, str) else raw_date.date().isoformat()
            
            hours = float(r.get("hoursUndertime", 0) or 0)
            if hours > 0:
                daily_max_undertime[date_str] = max(daily_max_undertime.get(date_str, 0.0), hours)
        
        total_hours = sum(daily_max_undertime.values())
        hourly_rate = (float(basic_salary) / 26.0) / 8.0
        return round(total_hours * hourly_rate, 2)

    @classmethod
    async def run_selective_payroll(cls, start_date: datetime, end_date: datetime, employee_ids: List[str]) -> int:
        collection = db["PayrollSnapshots"]
        processed_count = 0
        
        print(f"\n{'='*60}")
        print(f"🚀 PAYROLL RUN STARTED: {start_date.date()} to {end_date.date()}")
        print(f"Targeting {len(employee_ids)} employees...")
        print(f"{'='*60}")

        employees = await get_synced_active_employees()
        selected_map = {str(emp.id): emp for emp in employees if str(emp.id) in employee_ids}

        for emp_id, employee in selected_map.items():
            full_name = f"{employee.lastName}, {employee.firstName}"
            print(f"\n🔍 Processing: {full_name} ({employee.employeeId})")

            # 1. Overlap Check
            overlap_query = {"employee_id": employee.id, "pay_period_start": {"$lte": end_date}, "pay_period_end": {"$gte": start_date}}
            if await collection.find_one(overlap_query):
                print(f"   ⚠️  SKIPPED: Overlapping record found for this period.")
                continue

            # 2. Config & Rates
            config = await get_synced_employee_payroll_config(employee.id, employee.employeeId, full_name)
            if not config:
                print(f"   ❌ ERROR: No payroll configuration found.")
                continue
            
            print(f"   💰 Base Salary: PHP {config.basicSalary:,.2f}")
            
            # 3. Attendance Logs
            attendance_logs = await get_synced_attendance_list(employee.employeeId, start_date, end_date)
            attendance_dates = {datetime.fromisoformat(l.get("date")).date() if isinstance(l.get("date"), str) else l.get("date").date() for l in attendance_logs if l.get("date")}
            
            # 4. Compute Specific Components
            late_penalty_rate = float(getattr(config, "latePenaltyRate", 0) or 0)
            hr_late_penalties = cls._calculate_hr_late_penalties(attendance_logs, late_penalty_rate)
            late_penalty_items = cls._build_late_penalty_items(attendance_logs, late_penalty_rate)
            
            # Calculate total late hours from items for the snapshot
            total_late_hours = sum(item.get("late_hours", 0) for item in late_penalty_items)

            overtime_pay = await cls._calculate_synced_overtime_pay(employee.employeeId, start_date, end_date, config.basicSalary)
            undertime_deduction = await cls._calculate_synced_undertime_deduction(employee.employeeId, start_date, end_date, config.basicSalary)
            
            print(f"   ⏱️  Lates: PHP {hr_late_penalties:,.2f} ({total_late_hours:.2f}h) | UT: PHP {undertime_deduction:,.2f} | OT: PHP {overtime_pay:,.2f}")

            # 5. Holidays
            holidays_coll = db["Holidays"]
            holiday_docs = await holidays_coll.find({"date": {"$gte": start_date, "$lte": end_date}}).to_list(None)
            holidays = [Holiday(**h) for h in holiday_docs]
            
            expected_workdays = cls._count_weekdays(start_date, end_date)
            approved_leave_dates = await get_synced_approved_leave_dates(employee.employeeId, start_date, end_date)
            days_present = len(attendance_dates) + len(approved_leave_dates)
            
            print(f"   📅 Days: {days_present}/{expected_workdays} (Logs + Leaves)")

            # 6. Final Breakdown
            breakdown = await CompensationService.calculate_payroll_breakdown(
                config, expected_workdays=expected_workdays, days_present=days_present,
                holidays=holidays, hr_late_penalties=hr_late_penalties,
                overtime_pay=overtime_pay, undertime_deduction=undertime_deduction,
                attendance_dates=attendance_dates,
                late_hours=total_late_hours,
                late_items=late_penalty_items
            )

            print(f"   💵 Gross: {breakdown['gross_pay']:,.2f} | Net: {breakdown['net_pay']:,.2f}")

            # 7. Save Snapshot
            snapshot = PayrollSnapshot(
                employee_id=employee.id, employee_number=employee.employeeId,
                full_name=full_name, department=employee.department,
                **breakdown, pay_period_start=start_date, pay_period_end=end_date,
                days_worked=expected_workdays, days_present=days_present,
            )
            
            try:
                await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
                print(f"   ✅ SUCCESS: Snapshot created.")
                processed_count += 1
            except Exception as e:
                print(f"   ❌ DATABASE ERROR: {str(e)}")

        print(f"\n{'='*60}")
        print(f"🏁 RUN COMPLETE: Processed {processed_count} snapshots.")
        print(f"{'='*60}\n")
        return processed_count

    @classmethod
    async def get_payroll_readiness(cls) -> dict:
        employees = await get_synced_active_employees()
        results, ready_count, incomplete_count = [], 0, 0
        for emp in employees:
            full_name = f"{emp.lastName}, {emp.firstName}"
            config = await get_synced_employee_payroll_config(emp.id, emp.employeeId, full_name)
            
            missing_config = config is None
            issues = cls._validate_payroll_config(config) if config else ["No salary profile found in HR system."]
            
            is_ready = len(issues) == 0
            if is_ready: ready_count += 1
            else: incomplete_count += 1
            
            results.append({
                "id": str(emp.id),
                "employee_id": emp.employeeId,
                "full_name": full_name,
                "firstName": emp.firstName,
                "lastName": emp.lastName,
                "department": emp.department,
                "role": emp.role,
                "contractType": emp.contractType,
                "is_ready": is_ready,
                "issues": issues,
                "missing_config": missing_config,
                "basicSalary": config.basicSalary if config else 0.0,
                "housingAllowance": config.housingAllowance if config else 0.0,
                "transportAllowance": config.transportAllowance if config else 0.0,
                "mealAllowance": config.mealAllowance if config else 0.0,
                "otherAllowances": config.otherAllowances if config else 0.0,
                "sssLoan": config.sssLoan if config else 0.0,
                "pagIbigLoan": config.pagIbigLoan if config else 0.0,
                "companyLoan": config.companyLoan if config else 0.0
            })
        return {"ready_count": ready_count, "incomplete_count": incomplete_count, "employees": results}

    @classmethod
    async def get_payroll_history(cls, department: Optional[str] = None, period: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[PayrollSnapshot]:
        collection = db["PayrollSnapshots"]
        query = {}
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if start_date and end_date:
            query["processed_at"] = {"$gte": start_date, "$lte": end_date}
        elif period == "today":
            query["processed_at"] = {"$gte": today_start}
        elif period == "yesterday":
            yesterday_start = today_start - timedelta(days=1)
            query["processed_at"] = {"$gte": yesterday_start, "$lt": today_start}
        elif period == "week":
            query["processed_at"] = {"$gte": today_start - timedelta(days=7)}
        elif period == "month":
            query["processed_at"] = {"$gte": today_start - timedelta(days=30)}
            
        if department: query["department"] = department
        cursor = collection.find(query).sort("processed_at", -1)
        return [PayrollSnapshot(**doc) async for doc in cursor]

    @classmethod
    async def update_snapshot_status(cls, snapshot_id: str, status: str, remarks: Optional[str] = None) -> bool:
        collection = db["PayrollSnapshots"]
        update_data = {"status": status}
        if status == "Rejected":
            final_remarks = remarks or "Rejected by Finance Department."
            update_data["remarks"] = f"[Finance] {final_remarks}"
        elif remarks: update_data["remarks"] = remarks
        result = await collection.update_one({"_id": ObjectId(snapshot_id)}, {"$set": update_data})
        return result.modified_count > 0
