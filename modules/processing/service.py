import math
from datetime import datetime, timedelta
from typing import List, Optional
from core.database import db  # Access to OUR new database
from integrations.hr.adapter import get_all_active_employees, get_employee_payroll_config
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
        Counts Mon-Fri days in the pay period (inclusive).
        Used to replace the previous hard-coded workday assumption.
        """
        start_day = start_date.date()
        end_day = end_date.date()
        if end_day < start_day:
            return 0

        days = 0
        cursor = start_day
        while cursor <= end_day:
            if cursor.weekday() < 5:
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

    @classmethod
    async def get_payroll_readiness(cls) -> dict:
        """
        Scans all active employees and flags any issues that would cause a skip.
        Useful for the Wizard Step 2: Employee Selection.
        """
        employees = await get_all_active_employees()
        results = []
        ready_count = 0
        incomplete_count = 0

        for emp in employees:
            full_name = f"{emp.lastName}, {emp.firstName}"
            config = await get_employee_payroll_config(emp.id, emp.employeeId, full_name)
            
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
        employees = await get_all_active_employees()
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

            config = await get_employee_payroll_config(employee.id, employee.employeeId, full_name)
            if not config:
                print(f"WARNING: No payroll config found for {full_name}")
                continue

            issues = cls._validate_payroll_config(config)
            if issues:
                print(f"WARNING: Invalid payroll config for {full_name}: {', '.join(issues)}")
                continue

            # 1. Count Attendance from HR SYSTEM (Source of Truth)
            from integrations.hr.adapter import get_hr_attendance_count, get_hr_approved_leaves
            
            days_present_logs = await get_hr_attendance_count(employee.id, employee.employeeId, start_date, end_date)
            approved_leaves = await get_hr_approved_leaves(employee.id, start_date, end_date)
            
            # Total days present includes actual logs + approved paid leaves
            days_present = days_present_logs + approved_leaves
            expected_workdays = cls._count_weekdays(start_date, end_date)

            # 🛡️ ATTENDANCE REALITY GUARD
            if days_present > (expected_workdays + 4): # Allow 4 days for weekend/OT flexibility
                print(f"TRUTHFULNESS ALERT: {full_name} has {days_present}d present in a {expected_workdays}d period. Skipping suspicious record.")
                continue

            # 2. Perform calculations using attendance data
            breakdown = await CompensationService.calculate_payroll_breakdown(
                config, 
                employee.id,
                expected_workdays=expected_workdays,
                days_present=days_present
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
                pay_period_start=start_date,
                pay_period_end=end_date,
                days_worked=expected_workdays,
                days_present=days_present,
                days_absent=max(0, expected_workdays - days_present)
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
        from core.database import hr_db
        from integrations.hr.adapter import EMPLOYEES_COLLECTION
        from integrations.hr.schemas import HREmployeeRead
        from pydantic import ValidationError
        
        collection = db["PayrollSnapshots"]
        hr_coll = hr_db[EMPLOYEES_COLLECTION]
        
        obj_ids = [ObjectId(eid) for eid in employee_ids if ObjectId.is_valid(eid)]
        cursor = hr_coll.find({"_id": {"$in": obj_ids}, "isActive": True})
        
        processed_count = 0
        async for doc in cursor:
            try:
                employee = HREmployeeRead(**doc)
            except ValidationError as e:
                doc_id = doc.get("_id", "<unknown>")
                print(f"WARNING: Skipping invalid HR employee doc _id={doc_id}: {e}")
                continue
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

            config = await get_employee_payroll_config(employee.id, employee.employeeId, full_name)
            if not config:
                print(f"WARNING: No payroll config found for {full_name}")
                continue

            issues = cls._validate_payroll_config(config)
            if issues:
                print(f"WARNING: Invalid payroll config for {full_name}: {', '.join(issues)}")
                continue

            # 1. Count Attendance from HR SYSTEM (Source of Truth)
            from integrations.hr.adapter import get_hr_attendance_count, get_hr_approved_leaves
            
            days_present_logs = await get_hr_attendance_count(employee.id, employee.employeeId, start_date, end_date)
            approved_leaves = await get_hr_approved_leaves(employee.id, start_date, end_date)
            
            # Total days present includes actual logs + approved paid leaves
            days_present = days_present_logs + approved_leaves
            expected_workdays = cls._count_weekdays(start_date, end_date)

            # 🛡️ ATTENDANCE REALITY GUARD
            if days_present > (expected_workdays + 4): # Flexibility for OT/weekends
                print(f"TRUTHFULNESS ALERT: {full_name} has {days_present}d present in a {expected_workdays}d period. Skipping.")
                continue

            # 2. Perform calculations
            breakdown = await CompensationService.calculate_payroll_breakdown(
                config, 
                employee.id,
                expected_workdays=expected_workdays,
                days_present=days_present
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
                pay_period_start=start_date, pay_period_end=end_date,
                days_worked=expected_workdays,
                days_present=days_present,
                days_absent=max(0, expected_workdays - days_present)
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
