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

            # Perform calculations
            net_pay = await CompensationService.calculate_net_pay(config, employee.id)
            gross_pay = CompensationService.calculate_gross_pay(config)
            total_deductions = CompensationService.calculate_total_deductions(config)

            # Count Attendance for the Payslip
            attendance_coll = db["AttendanceLogs"]
            days_present = await attendance_coll.count_documents({
                "employee_id": employee.id,
                "date": {"$gte": start_date, "$lte": end_date},
                "status": "Approved"
            })
            expected_workdays = cls._count_weekdays(start_date, end_date)

            # Create Snapshot
            snapshot = PayrollSnapshot(
                employee_id=employee.id,
                employee_number=employee.employeeId,
                full_name=full_name,
                department=employee.department,
                basic_salary=config.basicSalary,
                gross_pay=gross_pay,
                total_deductions=total_deductions,
                net_pay=net_pay,
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

            net_pay = await CompensationService.calculate_net_pay(config, employee.id)
            gross_pay = CompensationService.calculate_gross_pay(config)
            total_deductions = CompensationService.calculate_total_deductions(config)

            attendance_coll = db["AttendanceLogs"]
            days_present = await attendance_coll.count_documents({
                "employee_id": employee.id,
                "date": {"$gte": start_date, "$lte": end_date},
                "status": "Approved"
            })
            expected_workdays = cls._count_weekdays(start_date, end_date)

            snapshot = PayrollSnapshot(
                employee_id=employee.id, employee_number=employee.employeeId,
                full_name=full_name, department=employee.department, basic_salary=config.basicSalary,
                gross_pay=gross_pay, total_deductions=total_deductions,
                net_pay=net_pay, pay_period_start=start_date, pay_period_end=end_date,
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
