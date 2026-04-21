import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from core.database import db
from integrations.hr.adapter import (
    get_all_active_employees,
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
        if end_day < start_day:
            return 0
        days = 0
        cursor = start_day
        while cursor <= end_day:
            if cursor.weekday() < 6:
                days += 1
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
        if value in (None, "", 0, 0.0, "0", "00:00", "00:00:00"):
            return 0.0
        if isinstance(value, (int, float)):
            numeric = float(value)
            if not math.isfinite(numeric) or numeric <= 0:
                return 0.0
            if "minute" in field_name.casefold():
                return round(numeric / 60.0, 4)
            return round(numeric, 4)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return 0.0
            if ":" in raw:
                parts = raw.split(":")
                try:
                    h, m = int(parts[0]), int(
                        parts[1]) if len(parts) > 1 else 0
                    s = int(parts[2]) if len(parts) > 2 else 0
                    return round((h * 3600 + m * 60 + s) / 3600.0, 4)
                except:
                    return 0.0
            try:
                numeric = float(raw)
                if numeric <= 0:
                    return 0.0
                if "minute" in field_name.casefold():
                    return round(numeric / 60.0, 4)
                return round(numeric, 4)
            except:
                return 0.0
        return 0.0

    @classmethod
    def _calculate_hr_late_penalties(cls, attendance_logs: list[dict], late_penalty_rate: float) -> float:
        """Calculates late penalties by taking the maximum late duration per day."""
        daily_max_lates = {}  # date_str -> max_late_hours

        for log in attendance_logs:
            raw_date = log.get("date")
            if not raw_date:
                raw_date = f"undated-{len(daily_max_lates)}"

            # Normalize date to YYYY-MM-DD
            date_str = raw_date.split("T")[0] if isinstance(
                raw_date, str) else raw_date.date().isoformat()

            for field_name in ("lateTime", "lateHours", "lateMinutes", "late", "tardiness"):
                if field_name not in log:
                    continue
                late_hours = cls._parse_late_duration_to_hours(
                    log.get(field_name), field_name)
                if late_hours > 0:
                    current_max = daily_max_lates.get(date_str, 0.0)
                    daily_max_lates[date_str] = max(current_max, late_hours)
                    break

        total_hours = sum(daily_max_lates.values())
        return round(total_hours * float(late_penalty_rate or 0), 2)

    @staticmethod
    def _count_payable_leave_days(approved_leave_dates: set, holiday_dates: set) -> int:
        """
        Counts paid leave days for the current six-day workweek setup.
        Sundays and holidays are excluded.
        """
        return sum(1 for leave_day in approved_leave_dates if leave_day.weekday() != 6 and leave_day not in holiday_dates)

    @classmethod
    def _build_late_penalty_items(cls, attendance_logs: list[dict], late_penalty_rate: float) -> list[dict]:
        """Groups late penalty details by day, taking only the maximum for each."""
        daily_max_items = {}  # date_str -> {late_hours, amount, raw_date}

        for log in attendance_logs:
            raw_date = log.get("date")
            if not raw_date:
                continue

            # Normalize date to YYYY-MM-DD
            date_str = raw_date.split("T")[0] if isinstance(
                raw_date, str) else raw_date.date().isoformat()

            for field_name in ("lateTime", "lateHours", "lateMinutes", "late", "tardiness"):
                if field_name not in log:
                    continue
                late_hours = cls._parse_late_duration_to_hours(
                    log.get(field_name), field_name)
                if late_hours <= 0:
                    continue

                if date_str not in daily_max_items or late_hours > daily_max_items[date_str]["late_hours"]:
                    # Capture the raw value if it's already a time string, otherwise format it
                    raw_val = log.get(field_name)
                    late_time_str = raw_val if (isinstance(
                        raw_val, str) and ":" in raw_val) else f"{int(late_hours)}:{int((late_hours*60) % 60):02d}"

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
    async def _calculate_synced_overtime_pay(cls, employee_number: str, start_date: datetime, end_date: datetime, basic_salary: float) -> tuple[float, float]:
        requests = await get_synced_overtime_requests(employee_number=employee_number, start_date=start_date, end_date=end_date)
        approved = [r for r in requests if str(
            r.get("status", "")).casefold() == "approved"]
        hourly_rate = ((float(basic_salary) / 26.0) / 8.0) * 1.25
        total_ot_hours = sum(cls._parse_overtime_hours(
            r.get("overtimeWorked")) for r in approved)
        return round(total_ot_hours * hourly_rate, 2), round(total_ot_hours, 2)

    @staticmethod
    def _calculate_night_diff_hours(time_in: datetime, time_out: datetime) -> float:
        """
        Calculates total hours worked between 10:00 PM and 6:00 AM.
        Handles shifts that cross midnight.
        """
        if not time_in or not time_out or time_out <= time_in:
            return 0.0

        total_nd_seconds = 0.0
        current_dt = time_in

        # We iterate in 15-minute chunks for precision while keeping performance
        # Alternatively, we can use intersection logic, but this is clearer for students.
        delta = timedelta(minutes=15)

        while current_dt < time_out:
            next_dt = min(current_dt + delta, time_out)

            # Check if the middle of this chunk is in the night window (22:00 - 06:00)
            # middle_hour = (current_dt + (next_dt - current_dt) / 2).hour
            # Use current_dt.hour directly as it's simpler
            hour = current_dt.hour
            if hour >= 22 or hour < 6:
                total_nd_seconds += (next_dt - current_dt).total_seconds()

            current_dt = next_dt

        return round(total_nd_seconds / 3600.0, 4)

    @staticmethod
    def _parse_overtime_hours(value) -> float:
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if ":" in str(value):
            parts = str(value).split(":")
            return int(parts[0]) + int(parts[1])/60.0
        return float(value)

    @classmethod
    async def _calculate_ytd_data(cls, employee_id: str, current_period_end: datetime, current_breakdown: dict) -> dict:
        """
        Calculates Year-To-Date (YTD) totals by summing previous snapshots in the same calendar year.
        """
        collection = db["PayrollSnapshots"]
        year_start = datetime(current_period_end.year,
                              1, 1, tzinfo=timezone.utc)

        # Query previous snapshots in the same year
        cursor = collection.find({
            "employee_id": employee_id,
            "pay_period_end": {"$gte": year_start, "$lt": current_period_end}
        })

        ytd = {
            "ytd_taxable_income": 0.0,
            "ytd_non_taxable_income": 0.0,
            "ytd_sss_contribution": 0.0,
            "ytd_phi_contribution": 0.0,
            "ytd_hdmf_contribution": 0.0,
            "ytd_wtax": 0.0
        }

        async for snapshot in cursor:
            # We derive taxable income sum (A) and non-taxable (B) from previous snapshots
            # In existing snapshots, we sum: basic_salary + total_overtime + holiday_pay + special_day_pay + excess_days_pay + total_nd_pay + retro_pay
            prev_taxable = (
                snapshot.get("basic_salary", 0) + 
                snapshot.get("total_overtime", 0) + 
                snapshot.get("total_nd_pay", 0) + 
                snapshot.get("holiday_pay", 0) + 
                snapshot.get("special_day_pay", 0) + 
                snapshot.get("excess_days_pay", 0) +
                snapshot.get("retro_pay", 0)
            )
            prev_non_taxable = (
                snapshot.get("housing_allowance", 0) + 
                snapshot.get("transport_allowance", 0) + 
                snapshot.get("meal_allowance", 0) + 
                snapshot.get("other_allowances", 0)
            )
            
            ytd["ytd_taxable_income"] += prev_taxable
            ytd["ytd_non_taxable_income"] += prev_non_taxable
            ytd["ytd_sss_contribution"] += snapshot.get("sss_deduction", 0)
            ytd["ytd_phi_contribution"] += snapshot.get("philhealth_deduction", 0)
            ytd["ytd_hdmf_contribution"] += snapshot.get("pagibig_deduction", 0)
            ytd["ytd_wtax"] += snapshot.get("withholding_tax", 0)
            
        # Add current period
        current_taxable = (
            current_breakdown.get("basic_salary", 0) + 
            current_breakdown.get("total_overtime", 0) + 
            current_breakdown.get("total_nd_pay", 0) + 
            current_breakdown.get("retro_pay", 0) +
            current_breakdown.get("holiday_pay", 0) + 
            current_breakdown.get("special_day_pay", 0) + 
            current_breakdown.get("excess_days_pay", 0)
        )
        current_non_taxable = (
            current_breakdown.get("housing_allowance", 0) +
            current_breakdown.get("transport_allowance", 0) +
            current_breakdown.get("meal_allowance", 0) +
            current_breakdown.get("other_allowances", 0)
        )

        ytd["ytd_taxable_income"] = round(
            ytd["ytd_taxable_income"] + current_taxable, 2)
        ytd["ytd_non_taxable_income"] = round(
            ytd["ytd_non_taxable_income"] + current_non_taxable, 2)
        ytd["ytd_sss_contribution"] = round(
            ytd["ytd_sss_contribution"] + current_breakdown.get("sss_deduction", 0), 2)
        ytd["ytd_phi_contribution"] = round(
            ytd["ytd_phi_contribution"] + current_breakdown.get("philhealth_deduction", 0), 2)
        ytd["ytd_hdmf_contribution"] = round(
            ytd["ytd_hdmf_contribution"] + current_breakdown.get("pagibig_deduction", 0), 2)
        ytd["ytd_wtax"] = round(
            ytd["ytd_wtax"] + current_breakdown.get("withholding_tax", 0), 2)

        return ytd

    @classmethod
    async def _calculate_synced_undertime_deduction(cls, employee_number: str, start_date: datetime, end_date: datetime, basic_salary: float) -> float:
        """Calculates undertime deductions by taking the maximum undertime hours per day."""
        records = await get_synced_undertime_records(employee_number=employee_number, start_date=start_date, end_date=end_date)

        daily_max_undertime = {}  # date_str -> max_hours
        for r in records:
            raw_date = r.get("date")
            if not raw_date:
                continue

            # Normalize date
            date_str = raw_date.split("T")[0] if isinstance(
                raw_date, str) else raw_date.date().isoformat()

            hours = float(r.get("hoursUndertime", 0) or 0)
            if hours > 0:
                daily_max_undertime[date_str] = max(
                    daily_max_undertime.get(date_str, 0.0), hours)

        total_hours = sum(daily_max_undertime.values())
        hourly_rate = (float(basic_salary) / 26.0) / 8.0
        return round(total_hours * hourly_rate, 2)

    @classmethod
    async def run_full_payroll(cls, start_date: datetime, end_date: datetime, pay_date: Optional[datetime] = None) -> int:
        """
        Processes payroll for ALL active employees.
        """
        employees = await get_all_active_employees()
        employee_ids = [str(emp.id) for emp in employees]
        return await cls.run_selective_payroll(start_date, end_date, employee_ids, pay_date=pay_date)

    @classmethod
    async def run_selective_payroll(cls, start_date: datetime, end_date: datetime, employee_ids: List[str], pay_date: Optional[datetime] = None) -> int:
        collection = db["PayrollSnapshots"]
        processed_count = 0

        print(f"\n{'='*60}")
        print(
            f"🚀 PAYROLL RUN STARTED: {start_date.date()} to {end_date.date()}")
        if pay_date:
            print(f"💰 Scheduled Payday: {pay_date.date()}")
        print(f"Targeting {len(employee_ids)} employees...")
        print(f"{'='*60}")

        employees = await get_all_active_employees()
        selected_map = {str(emp.id): emp for emp in employees if str(
            emp.id) in employee_ids}

        for emp_id, employee in selected_map.items():
            full_name = f"{employee.lastName}, {employee.firstName}"
            print(f"\n🔍 Processing: {full_name} ({employee.employeeId})")

            # 1. Overlap Check
            overlap_query = {"employee_id": employee.id, "pay_period_start": {
                "$lte": end_date}, "pay_period_end": {"$gte": start_date}}
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
            attendance_dates = {datetime.fromisoformat(l.get("date")).date() if isinstance(l.get(
                "date"), str) else l.get("date").date() for l in attendance_logs if l.get("date")}

            # 4. Compute Specific Components
            late_penalty_rate = float(
                getattr(config, "latePenaltyRate", 0) or 0)
            hr_late_penalties = cls._calculate_hr_late_penalties(
                attendance_logs, late_penalty_rate)
            late_penalty_items = cls._build_late_penalty_items(
                attendance_logs, late_penalty_rate)

            # Calculate total late hours from items for the snapshot
            total_late_hours = sum(item.get("late_hours", 0)
                                   for item in late_penalty_items)

            daily_rate = float(config.basicSalary) / 26.0
            hourly_rate = round(daily_rate / 8.0, 2)

            overtime_pay, overtime_hours = await cls._calculate_synced_overtime_pay(employee.employeeId, start_date, end_date, config.basicSalary)
            undertime_deduction = await cls._calculate_synced_undertime_deduction(employee.employeeId, start_date, end_date, config.basicSalary)

            # 🚀 NEW: Night Differential Calculation
            total_nd_hours = 0.0
            for log in attendance_logs:
                time_in = log.get("timeIn")
                time_out = log.get("timeOut")
                if isinstance(time_in, str):
                    time_in = datetime.fromisoformat(time_in)
                if isinstance(time_out, str):
                    time_out = datetime.fromisoformat(time_out)
                total_nd_hours += cls._calculate_night_diff_hours(
                    time_in, time_out)

            nd_multiplier = float(
                getattr(config, "nightDifferentialRate", 0.10) or 0.10)
            total_nd_pay = round(
                total_nd_hours * hourly_rate * nd_multiplier, 2)

            print(f"   ⏱️  Lates: PHP {hr_late_penalties:,.2f} ({total_late_hours:.2f}h) | UT: PHP {undertime_deduction:,.2f} | OT: PHP {overtime_pay:,.2f} ({overtime_hours:.2f}h) | ND: PHP {total_nd_pay:,.2f} ({total_nd_hours:.2f}h)")

            # 🚀 NEW: Retroactive Adjustments
            # Use string matching to ensure we catch adjustments regardless of ID source
            adj_query = {
                "employee_id": {"$in": [str(employee.id), str(getattr(employee, "id", "")), employee.employeeId]},
                "is_applied": False
            }
            adjustments_cursor = db["ManualAdjustments"].find(adj_query)
            adjustments = await adjustments_cursor.to_list(None)
            retro_pay = sum(float(adj.get("amount", 0)) for adj in adjustments)
            retro_items = [{"amount": float(adj.get("amount", 0)), "reason": adj.get("reason", "Adjustment")} for adj in adjustments]
            
            if retro_pay != 0:
                print(f"   🔄 Retroactive Adjustment: PHP {retro_pay:,.2f} ({len(adjustments)} items)")

            # 5. Holidays
            holidays_coll = db["Holidays"]
            holiday_docs = await holidays_coll.find({"date": {"$gte": start_date, "$lte": end_date}}).to_list(None)
            holidays = [Holiday(**h) for h in holiday_docs]

            expected_workdays = cls._count_weekdays(start_date, end_date)
            approved_leave_dates = await get_synced_approved_leave_dates(employee.employeeId, start_date, end_date)
            days_present = len(attendance_dates) + len(approved_leave_dates)

            print(
                f"   📅 Days: {days_present}/{expected_workdays} (Logs + Leaves)")

            # 6. Final Breakdown
            breakdown = await CompensationService.calculate_payroll_breakdown(
                config, expected_workdays=expected_workdays, days_present=days_present,
                pay_period_start=start_date, pay_period_end=end_date,
                holidays=holidays, hr_late_penalties=hr_late_penalties,
                overtime_pay=overtime_pay, undertime_deduction=undertime_deduction,
                total_nd_pay=total_nd_pay,
                retro_pay=retro_pay,
                attendance_dates=attendance_dates,
                approved_leave_dates=approved_leave_dates,
                late_hours=total_late_hours,
                late_items=late_penalty_items
            )

            print(
                f"   💵 Gross: {breakdown['gross_pay']:,.2f} | Net: {breakdown['net_pay']:,.2f}")

            # 🚀 NEW: Calculate YTD Data
            ytd_data = await cls._calculate_ytd_data(str(employee.id), end_date, breakdown)

            # 7. Save Snapshot
            snapshot = PayrollSnapshot(
                employee_id=employee.id, employee_number=employee.employeeId,
                full_name=full_name, department=employee.department,
                sss_number=getattr(employee, "sssNumber", None),
                philhealth_number=getattr(employee, "philHealthNumber", None),
                pagibig_number=getattr(employee, "pagIbigNumber", None),
                basic_pay_hours=float(days_present * 8.0),
                total_overtime_hours=overtime_hours,
                total_nd_hours=total_nd_hours,
                hourly_rate=hourly_rate,
                ytd_data=ytd_data,
                retro_items=retro_items,
                **breakdown, pay_period_start=start_date, pay_period_end=end_date,
                pay_date=pay_date,
                days_worked=expected_workdays, days_present=days_present,
            )

            try:
                result = await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
                snapshot_id = str(result.inserted_id)
                print(f"   ✅ SUCCESS: Snapshot created.")

                # Mark adjustments as processed
                if adjustments:
                    await db["ManualAdjustments"].update_many(
                        {"_id": {"$in": [adj["_id"] for adj in adjustments]}},
                        {"$set": {"is_applied": True,
                                  "applied_on_snapshot_id": snapshot_id}}
                    )

                processed_count += 1
            except Exception as e:
                print(f"   ❌ DATABASE ERROR: {str(e)}")

        print(f"\n{'='*60}")
        print(f"🏁 RUN COMPLETE: Processed {processed_count} snapshots.")
        print(f"{'='*60}\n")
        return processed_count

    @classmethod
    async def get_payroll_readiness(cls) -> dict:
        employees = await get_all_active_employees()
        results, ready_count, incomplete_count = [], 0, 0
        for emp in employees:
            full_name = f"{emp.lastName}, {emp.firstName}"
            config = await get_synced_employee_payroll_config(emp.id, emp.employeeId, full_name)

            missing_config = config is None
            issues = cls._validate_payroll_config(config) if config else [
                "No salary profile found in HR system."]

            is_ready = len(issues) == 0
            if is_ready:
                ready_count += 1
            else:
                incomplete_count += 1

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
            query["processed_at"] = {
                "$gte": yesterday_start, "$lt": today_start}
        elif period == "week":
            query["processed_at"] = {"$gte": today_start - timedelta(days=7)}
        elif period == "month":
            query["processed_at"] = {"$gte": today_start - timedelta(days=30)}

        if department:
            query["department"] = department
        cursor = collection.find(query).sort("processed_at", -1)
        return [PayrollSnapshot(**doc) async for doc in cursor]

    @classmethod
    async def update_snapshot_status(cls, snapshot_id: str, status: str, remarks: Optional[str] = None) -> bool:
        collection = db["PayrollSnapshots"]
        update_data = {"status": status}
        if status == "Rejected":
            final_remarks = remarks or "Rejected by Finance Department."
            update_data["remarks"] = f"[Finance] {final_remarks}"
        elif remarks:
            update_data["remarks"] = remarks
        result = await collection.update_one({"_id": ObjectId(snapshot_id)}, {"$set": update_data})
        return result.modified_count > 0
