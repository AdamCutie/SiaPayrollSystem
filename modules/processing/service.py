from datetime import datetime
from typing import List
from core.database import db  # Access to OUR new database
from integrations.hr.adapter import get_all_active_employees, get_employee_payroll_config
from modules.compensation.service import CompensationService
from db.models import PayrollSnapshot  # Access to our storage model


class PayrollProcessingService:
    """
    Orchestrates the payroll run and saves results to our new database.
    This is the 'Bridge' between HR data and Payroll storage.
    """

    @classmethod
    async def run_full_payroll(cls, start_date: datetime, end_date: datetime) -> int:
        """
        Executes a payroll run, calculates net pay, and saves snapshots to DB.
        Returns the total count of processed employees.
        """
        # Access OUR new collection for payroll records
        collection = db["PayrollSnapshots"]

        # Get active employees from the legacy HR system (Read-Only)
        employees = await get_all_active_employees()
        processed_count = 0

        for employee in employees:
            # Fetch their specific salary configuration from HR
            config = await get_employee_payroll_config(employee.id)
            if not config:
                print(
                    f"WARNING: No payroll config found for {employee.firstName} {employee.lastName}")
                continue

            # Perform calculations using our Math Service
            net_pay = CompensationService.calculate_net_pay(config)
            gross_pay = CompensationService.calculate_gross_pay(config)
            total_deductions = CompensationService.calculate_total_deductions(
                config)

            # Create the 'Snapshot' object (The Receipt)
            snapshot = PayrollSnapshot(
                employee_id=employee.id,
                employee_number=employee.employeeId,
                full_name=f"{employee.lastName}, {employee.firstName}",
                basic_salary=config.basicSalary,
                gross_pay=gross_pay,
                total_deductions=total_deductions,
                net_pay=net_pay,
                pay_period_start=start_date,
                pay_period_end=end_date
            )

            # SAVE to our NEW MongoDB database
            # .model_dump(by_alias=True) converts the Pydantic object to a MongoDB dictionary
            # We exclude 'id' during insertion so MongoDB generates its own _id
            await collection.insert_one(snapshot.model_dump(by_alias=True, exclude={"id"}))
            processed_count += 1

        return processed_count
