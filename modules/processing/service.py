from datetime import datetime
from typing import List
from core.database import db  # Access to OUR new database
from integrations.hr.adapter import get_all_active_employees, get_employee_payroll_config
from modules.compensation.service import CompensationService
from db.models import PayrollSnapshot  # Access to our storage model


class PayrollProcessingService:
    """
    Orchestrates the payroll run and saves results to our new database.
    """

    @classmethod
    async def run_full_payroll(cls, start_date: datetime, end_date: datetime) -> int:
        """
        Executes a payroll run, calculates net pay, and saves snapshots to DB.
        """
        collection = db["PayrollSnapshots"]
        employees = await get_all_active_employees()
        processed_count = 0

        for employee in employees:
            full_name = f"{employee.lastName}, {employee.firstName}"

            # Use ID, Number, and Name to find the configuration
            config = await get_employee_payroll_config(employee.id, employee.employeeId, full_name)

            if not config:
                print(f"WARNING: No payroll config found for {full_name}")
                continue

            # Perform calculations
            net_pay = CompensationService.calculate_net_pay(config)
            gross_pay = CompensationService.calculate_gross_pay(config)
            total_deductions = CompensationService.calculate_total_deductions(
                config)

            # Create Snapshot
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

            # SAVE to our NEW database
            await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
            processed_count += 1

        return processed_count

    @classmethod
    async def get_payroll_history(cls) -> List[PayrollSnapshot]:
        """
        Fetches all past payroll snapshots from our new
        database.
        Sorted by the most recently processed first (-1).
        """
        # Access the collection in Our new database
        collection = db["PayrollSnapshots"]

        # Find all records and sort by processing time(Newest First)
        cursor = collection.find().sort("processed_at", -1)
        history = []
        async for doc in cursor:
            # Wrap each raw MongoDB dictionary into our Snapshot Model
            history.append(PayrollSnapshot(**doc))

        return history
