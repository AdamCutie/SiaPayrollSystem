import math
from datetime import datetime, timedelta
from typing import List, Optional
from core.database import db  # Access to OUR new database
from integrations.hr.adapter import (
    get_synced_active_employees,
    get_synced_attendance_list,
    get_synced_approved_leave_dates,
    get_synced_employee_payroll_config,
    get_synced_overtime_requests,
)
from modules.compensation.service import CompensationService
from db.models import PayrollSnapshot  # Access to our storage model
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

class PayrollProcessingService:
    """
    Orchestrates the payroll run and saves results to our new database.
    Includes duplicate prevention to ensure employees aren't paid twice for the same period.
    """

    @staticmethod
    def _count_weekdays(start_date: datetime, end_date: datetime) -> int:
        """
        Counts Mon-Sat days in the pay period (inclusive).
        """
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
        """
        Defensive validation for integration data. If HR data is wrong,
        we skip that employee instead of producing incorrect payroll.
        """
        issues: list[str] = []

        def check_positive(field: str, value: float) -> None:
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
                issues.append(f"{field} must be > 0")

        def check_non_negative(field: str, value: float) -> None:
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
                issues.append(f"{field} must be >= 0")

        check_positive("basicSalary", config.basicSalary)

        # Allowances
        check_non_negative("housingAllowance", config.housingAllowance)
        check_non_negative("transportAllowance", config.transportAllowance)
        check_non_negative("mealAllowance", config.mealAllowance)
        check_non_negative("otherAllowances", config.otherAllowances)

        # Deductions / contributions / taxes
        check_non_negative("sssContribution", config.sssContribution)
        check_non_negative("philHealthContribution", config.philHealthContribution)
        check_non_negative("pagIbigContribution", config.pagIbigContribution)
        check_non_negative("withholdingTax", config.withholdingTax)

        # Loans
        check_non_negative("sssLoan", config.sssLoan)
        check_non_negative("pagIbigLoan", config.pagIbigLoan)
        check_non_negative("companyLoan", config.companyLoan)

        # Penalty rates
        check_non_negative("absencePenaltyRate", config.absencePenaltyRate)
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
                return round(numeric / 60.0, 2)
            return round(numeric, 2)

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return 0.0

            if ":" in raw:
                parts = raw.split(":")
                try:
                    h = int(parts[0])
                    m = int(parts[1]) if len(parts) > 1 else 0
                    s = int(parts[2]) if len(parts) > 2 else 0
                    total_seconds = (h * 3600) + (m * 60) + s
                    return round(total_seconds / 3600.0, 2)
                except ValueError:
                    return 0.0

            try:
                numeric = float(raw)
            except ValueError:
                return 0.0

            if numeric <= 0:
                return 0.0
            if "minute" in field_name.casefold():
                return round(numeric / 60.0, 2)
            return round(numeric, 2)

        return 0.0

    @classmethod
    def _calculate_hr_late_penalties(cls, attendance_logs: list[dict], late_penalty_rate: float) -> float:
        total = 0.0
        for log in attendance_logs:
            for field_name in ("lateTime", "lateHours", "lateMinutes", "late", "tardiness"):
                if field_name not in log:
                    continue
                late_hours = cls._parse_late_duration_to_hours(log.get(field_name), field_name)
                if late_hours > 0:
                    total += late_hours * float(late_penalty_rate or 0)
                    break
        return round(total, 2)

    @classmethod
    def _build_late_penalty_items(cls, attendance_logs: list[dict], late_penalty_rate: float) -> list[dict]:
        items: list[dict] = []
        for log in attendance_logs:
            for field_name in ("lateTime", "lateHours", "lateMinutes", "late", "tardiness"):
                if field_name not in log:
                    continue
                late_hours = cls._parse_late_duration_to_hours(log.get(field_name), field_name)
                if late_hours <= 0:
                    continue
                late_date = cls._parse_hr_log_date(log.get("date"))
                raw_value = log.get(field_name)
                display_value = raw_value if isinstance(raw_value, str) else f"{late_hours:.2f}h"
                items.append(
                    {
                        "date": late_date.isoformat() if late_date else None,
                        "late_time": display_value,
                        "late_hours": round(late_hours, 2),
                        "rate": round(float(late_penalty_rate or 0), 2),
                        "amount": round(late_hours * float(late_penalty_rate or 0), 2),
                        "source_field": field_name,
                    }
                )
                break
        return items

    @staticmethod
    def _parse_hr_log_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except ValueError:
                try:
                    return datetime.fromisoformat(value.split("T")[0]).date()
                except ValueError:
                    return None
        return None

    @classmethod
    def _attendance_dates_from_logs(cls, attendance_logs: list[dict]) -> set:
        return {
            parsed
            for log in attendance_logs
            for parsed in [cls._parse_hr_log_date(log.get("date"))]
            if parsed is not None
        }

    @staticmethod
    def _count_payable_leave_days(approved_leave_dates: set, holiday_dates: set) -> int:
        return sum(
            1
            for leave_day in approved_leave_dates
            if leave_day.weekday() < 6 and leave_day not in holiday_dates
        )

    @staticmethod
    def _build_worked_holiday_items(holidays: list, attendance_dates: set, daily_rate: float) -> list[dict]:
        items: list[dict] = []
        for holiday in holidays:
            holiday_day = holiday.date.date()
            if holiday_day not in attendance_dates:
                continue
            multiplier = 1.0 if holiday.type == "Regular Holiday" else 0.3
            items.append(
                {
                    "date": holiday_day.isoformat(),
                    "name": holiday.name,
                    "type": holiday.type,
                    "amount": round(daily_rate * multiplier, 2),
                }
            )
        return items

    @staticmethod
    def _parse_overtime_hours(value) -> float:
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        if isinstance(value, str) and ":" in value:
            parts = value.split(":")
            try:
                hours = int(parts[0])
                minutes = int(parts[1]) if len(parts) > 1 else 0
                seconds = int(parts[2]) if len(parts) > 2 else 0
                return round(hours + (minutes / 60.0) + (seconds / 3600.0), 2)
            except ValueError:
                return 0.0
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    async def _calculate_synced_overtime_pay(
        cls,
        employee_number: str,
        start_date: datetime,
        end_date: datetime,
        basic_salary: float,
    ) -> float:
        requests = await get_synced_overtime_requests(
            employee_number=employee_number,
            start_date=start_date,
            end_date=end_date,
        )
        approved_requests = [
            req for req in requests
            if str(req.get("status", "")).casefold() == "approved"
        ]
        hourly_rate = ((float(basic_salary) / 26.0) / 8.0) * 1.25
        total_pay = 0.0
        for req in approved_requests:
            total_pay += cls._parse_overtime_hours(req.get("overtimeWorked")) * hourly_rate
        return round(total_pay, 2)

    @classmethod
    async def get_payroll_readiness(cls) -> dict:
        """
        Scans all active employees and flags any issues that would cause a skip.
        Useful for the Wizard Step 2: Employee Selection.
        """
        employees = await get_synced_active_employees()
        results = []
        ready_count = 0
        incomplete_count = 0

        for emp in employees:
            full_name = f"{emp.lastName}, {emp.firstName}"
            config = await get_synced_employee_payroll_config(emp.id, emp.employeeId, full_name)
            
            issues = []
            missing_config = False
            
            if not config:
                issues.append("No salary profile found in HR system.")
                missing_config = True
            else:
                issues = cls._validate_payroll_config(config)
            
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
                "basicSalary": config.basicSalary if config else 0,
                "housingAllowance": config.housingAllowance if config else 0,
                "transportAllowance": config.transportAllowance if config else 0,
                "mealAllowance": config.mealAllowance if config else 0,
                "otherAllowances": config.otherAllowances if config else 0,
                "sssLoan": config.sssLoan if config else 0,
                "pagIbigLoan": config.pagIbigLoan if config else 0,
                "companyLoan": config.companyLoan if config else 0
            })
            
        return {
            "ready_count": ready_count,
            "incomplete_count": incomplete_count,
            "employees": results
        }

    @classmethod
    async def run_full_payroll(cls, start_date: datetime, end_date: datetime) -> int:
        """
        Executes a payroll run for all active employees.
        """
        collection = db["PayrollSnapshots"]
        employees = await get_synced_active_employees()
        processed_count = 0

        for employee in employees:
            full_name = f"{employee.lastName}, {employee.firstName}"
            
            # 🚀 DUPLICATE CHECK: Prevent double-paying for the same period
            existing = await collection.find_one({
                "employee_id": employee.id,
                "pay_period_start": start_date,
                "pay_period_end": end_date
            })
            if existing:
                print(f"SKIPPING: {full_name} already has a snapshot for this period.")
                continue

            config = await get_synced_employee_payroll_config(employee.id, employee.employeeId, full_name)
            if not config:
                print(f"WARNING: No payroll config found for {full_name}")
                continue

            issues = cls._validate_payroll_config(config)
            if issues:
                print(f"WARNING: Invalid payroll config for {full_name}: {', '.join(issues)}")
                continue

            # 1. Count Attendance from HR SYSTEM (Source of Truth)
            from db.models import Holiday
            attendance_logs = await get_synced_attendance_list(employee.employeeId, start_date, end_date)
            attendance_dates = cls._attendance_dates_from_logs(attendance_logs)
            hr_late_penalties = cls._calculate_hr_late_penalties(
                attendance_logs,
                float(getattr(config, "latePenaltyRate", 0) or 0),
            )
            late_penalty_rate = float(getattr(config, "latePenaltyRate", 0) or 0)
            late_penalty_items = cls._build_late_penalty_items(attendance_logs, late_penalty_rate)
            overtime_pay = await cls._calculate_synced_overtime_pay(
                employee.employeeId,
                start_date,
                end_date,
                config.basicSalary,
            )
            
            # Fetch Holidays in this period
            holidays_coll = db["Holidays"]
            holiday_docs = await holidays_coll.find({"date": {"$gte": start_date, "$lte": end_date}}).to_list(None)
            holidays = [Holiday(**h) for h in holiday_docs]
            holiday_dates = {holiday.date.date() for holiday in holidays}
            approved_leave_dates = await get_synced_approved_leave_dates(employee.employeeId, start_date, end_date)
            approved_work_leave_days = cls._count_payable_leave_days(approved_leave_dates, holiday_dates)
            days_present_logs = len(attendance_dates)
            daily_rate = round(float(config.basicSalary) / 26.0, 2)
            worked_holiday_items = cls._build_worked_holiday_items(holidays, attendance_dates, daily_rate)

            # Total days present includes actual logs + approved paid leaves
            days_present = days_present_logs + approved_work_leave_days
            expected_workdays = cls._count_weekdays(start_date, end_date)

            # 🛡️ ATTENDANCE REALITY GUARD
            if days_present > (expected_workdays + 4): # Allow 4 days for weekend/OT flexibility
                print(f"TRUTHFULNESS ALERT: {full_name} has {days_present}d present in a {expected_workdays}d period. Skipping suspicious record.")
                continue

            # 2. Perform calculations using attendance data
            breakdown = await CompensationService.calculate_payroll_breakdown(
                config, 
                expected_workdays=expected_workdays,
                days_present=days_present,
                holidays=holidays,
                hr_late_penalties=hr_late_penalties,
                overtime_pay=overtime_pay,
                attendance_dates=attendance_dates,
            )

            # 🛡️ NEGATIVE PAY GUARD
            if breakdown["net_pay"] < 0:
                print(f"FINANCIAL PROTECTION: {full_name} resulted in negative net pay (₱{breakdown['net_pay']}). Skipping to prevent debt generation.")
                continue

            # 3. Create Snapshot
            snapshot = PayrollSnapshot(
                employee_id=employee.id,
                employee_number=employee.employeeId,
                full_name=full_name,
                department=employee.department,
                **breakdown, # Spreads all itemized fields from breakdown
                total_late_hours=round(sum(item["late_hours"] for item in late_penalty_items), 2),
                late_penalty_rate=late_penalty_rate,
                late_penalty_items=late_penalty_items,
                worked_holiday_items=worked_holiday_items,
                zero_net_reason=(
                    "Take-home pay was reduced to 0.00 because total deductions and penalties exceeded gross pay for this period."
                    if breakdown["gross_pay"] <= (breakdown["total_deductions"] + breakdown["total_penalties"])
                    else None
                ),
                pay_period_start=start_date,
                pay_period_end=end_date,
                days_worked=expected_workdays,
                days_present=days_present,
            )

            try:
                await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
            except DuplicateKeyError:
                # Another concurrent run inserted the same snapshot; treat as a clean skip.
                print(f"SKIPPING: {full_name} already has a snapshot for this period (unique index).")
                continue

            processed_count += 1

        return processed_count

    @classmethod
    async def run_selective_payroll(cls, start_date: datetime, end_date: datetime, employee_ids: List[str]) -> int:
        """
        Executes a payroll run for a SPECIFIC list of employees (Figma Wizard Step 2).
        """
        collection = db["PayrollSnapshots"]
        selected_ids = set(employee_ids)
        employees = [emp for emp in await get_synced_active_employees() if emp.id in selected_ids]

        processed_count = 0
        for employee in employees:
            full_name = f"{employee.lastName}, {employee.firstName}"
            
            # 🚀 DUPLICATE CHECK: Prevent double-paying
            existing = await collection.find_one({
                "employee_id": employee.id,
                "pay_period_start": start_date,
                "pay_period_end": end_date
            })
            if existing:
                print(f"SKIPPING: {full_name} already has a snapshot for this period.")
                continue

            config = await get_synced_employee_payroll_config(employee.id, employee.employeeId, full_name)
            if not config:
                print(f"WARNING: No payroll config found for {full_name}")
                continue

            issues = cls._validate_payroll_config(config)
            if issues:
                print(f"WARNING: Invalid payroll config for {full_name}: {', '.join(issues)}")
                continue

            # 1. Count Attendance from HR SYSTEM (Source of Truth)
            from db.models import Holiday
            attendance_logs = await get_synced_attendance_list(employee.employeeId, start_date, end_date)
            attendance_dates = cls._attendance_dates_from_logs(attendance_logs)
            hr_late_penalties = cls._calculate_hr_late_penalties(
                attendance_logs,
                float(getattr(config, "latePenaltyRate", 0) or 0),
            )
            late_penalty_rate = float(getattr(config, "latePenaltyRate", 0) or 0)
            late_penalty_items = cls._build_late_penalty_items(attendance_logs, late_penalty_rate)
            overtime_pay = await cls._calculate_synced_overtime_pay(
                employee.employeeId,
                start_date,
                end_date,
                config.basicSalary,
            )
            
            # Fetch Holidays in this period
            holidays_coll = db["Holidays"]
            holiday_docs = await holidays_coll.find({"date": {"$gte": start_date, "$lte": end_date}}).to_list(None)
            holidays = [Holiday(**h) for h in holiday_docs]
            holiday_dates = {holiday.date.date() for holiday in holidays}
            approved_leave_dates = await get_synced_approved_leave_dates(employee.employeeId, start_date, end_date)
            approved_work_leave_days = cls._count_payable_leave_days(approved_leave_dates, holiday_dates)
            days_present_logs = len(attendance_dates)
            daily_rate = round(float(config.basicSalary) / 26.0, 2)
            worked_holiday_items = cls._build_worked_holiday_items(holidays, attendance_dates, daily_rate)

            # Total days present includes actual logs + approved paid leaves
            days_present = days_present_logs + approved_work_leave_days
            expected_workdays = cls._count_weekdays(start_date, end_date)

            # 🛡️ ATTENDANCE REALITY GUARD
            if days_present > (expected_workdays + 4): # Flexibility for OT/weekends
                print(f"TRUTHFULNESS ALERT: {full_name} has {days_present}d present in a {expected_workdays}d period. Skipping.")
                continue

            # 2. Perform calculations
            breakdown = await CompensationService.calculate_payroll_breakdown(
                config, 
                expected_workdays=expected_workdays,
                days_present=days_present,
                holidays=holidays,
                hr_late_penalties=hr_late_penalties,
                overtime_pay=overtime_pay,
                attendance_dates=attendance_dates,
            )

            # 🛡️ NEGATIVE PAY GUARD
            if breakdown["net_pay"] < 0:
                print(f"FINANCIAL PROTECTION: {full_name} resulted in negative net pay (₱{breakdown['net_pay']}). Skipping.")
                continue

            # 3. Create Snapshot
            snapshot = PayrollSnapshot(
                employee_id=employee.id, employee_number=employee.employeeId,
                full_name=full_name, department=employee.department,
                **breakdown,
                total_late_hours=round(sum(item["late_hours"] for item in late_penalty_items), 2),
                late_penalty_rate=late_penalty_rate,
                late_penalty_items=late_penalty_items,
                worked_holiday_items=worked_holiday_items,
                zero_net_reason=(
                    "Take-home pay was reduced to 0.00 because total deductions and penalties exceeded gross pay for this period."
                    if breakdown["gross_pay"] <= (breakdown["total_deductions"] + breakdown["total_penalties"])
                    else None
                ),
                pay_period_start=start_date, pay_period_end=end_date,
                days_worked=expected_workdays,
                days_present=days_present,
            )

            try:
                await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
            except DuplicateKeyError:
                print(f"SKIPPING: {full_name} already has a snapshot for this period (unique index).")
                continue

            processed_count += 1

        return processed_count

    @classmethod
    async def get_payroll_history(cls, department: Optional[str] = None) -> List[PayrollSnapshot]:
        """
        Fetches payroll history with optional department filtering.
        """
        collection = db["PayrollSnapshots"]
        query = {}
        if department:
            query["department"] = department
            
        cursor = collection.find(query).sort("processed_at", -1)
        return [PayrollSnapshot(**doc) async for doc in cursor]
