from datetime import datetime
from typing import List, Optional
from core.database import db  # Access to OUR new database
from integrations.hr.adapter import get_all_active_employees, get_employee_payroll_config
from modules.compensation.service import CompensationService
from db.models import PayrollSnapshot  # Access to our storage model
from bson import ObjectId

class PayrollProcessingService:
    """
    Orchestrates the payroll run and saves results to our new database.
    """

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
            config = await get_employee_payroll_config(employee.id, employee.employeeId, full_name)

            if not config:
                print(f"WARNING: No payroll config found for {full_name}")
                continue

            net_pay = await CompensationService.calculate_net_pay(config)
            gross_pay = CompensationService.calculate_gross_pay(config)
            total_deductions = CompensationService.calculate_total_deductions(config)

            snapshot = PayrollSnapshot(
                employee_id=employee.id,
                employee_number=employee.employeeId,
                full_name=full_name,
                basic_salary=config.basicSalary,
                gross_pay=gross_pay,
                total_deductions=total_deductions,
                net_pay=net_pay,
                pay_period_start=start_date,
                pay_period_end=end_date
            )

            await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
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
        
        collection = db["PayrollSnapshots"]
        hr_coll = hr_db[EMPLOYEES_COLLECTION]
        
        # Match only selected IDs
        obj_ids = [ObjectId(eid) for eid in employee_ids if ObjectId.is_valid(eid)]
        cursor = hr_coll.find({"_id": {"$in": obj_ids}, "isActive": True})
        
        processed_count = 0
        async for doc in cursor:
            employee = HREmployeeRead(**doc)
            full_name = f"{employee.lastName}, {employee.firstName}"
            config = await get_employee_payroll_config(employee.id, employee.employeeId, full_name)
            
            if not config: continue

            net_pay = await CompensationService.calculate_net_pay(config)
            gross_pay = CompensationService.calculate_gross_pay(config)
            total_deductions = CompensationService.calculate_total_deductions(config)

            snapshot = PayrollSnapshot(
                employee_id=employee.id, employee_number=employee.employeeId,
                full_name=full_name, basic_salary=config.basicSalary,
                gross_pay=gross_pay, total_deductions=total_deductions,
                net_pay=net_pay, pay_period_start=start_date, pay_period_end=end_date
            )

            await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
            processed_count += 1

        return processed_count

    @classmethod
    async def get_payroll_history(cls, department: Optional[str] = None) -> List[PayrollSnapshot]:
        """
        Fetches payroll history with optional department filtering (Figma Sorter).
        """
        collection = db["PayrollSnapshots"]
        query = {}
        if department:
            query["department"] = department # Snapshot would need department field updated
            
        cursor = collection.find(query).sort("processed_at", -1)
        return [PayrollSnapshot(**doc) async for doc in cursor]
