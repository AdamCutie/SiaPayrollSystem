from typing import List, Dict
from integrations.hr.adapter import get_all_active_employees, get_employee_payroll_config
from modules.compensation.service import CompensationService


class PayrollProcessingService:
    """
    The Orchestrator. This service coordinates between the HR Adapter
    and the Compensation Service to generate payroll for
    the entire company.
    """

    @classmethod
    async def run_full_payroll(cls) -> List[Dict]:
        """
        Executes a payroll run for all active employees.
        """
        # Fetch all active employees from the legacy HR system
        employees = await get_all_active_employees()

        payroll_results = []

        # loop through each employee one by one
        for employee in employees:
            # Fetch their specific salary configuration
            config = await get_employee_payroll_config(employee.id)
            if not config:
                # if an employee  exists but has no salary setup, skip them(or log an error)
                print(
                    f"WARNING: No payroll config found for {employee.firstName} {employee.lastName}")
                continue
            # Perform the calculations using our Compensation Service
            net_pay = CompensationService.calculate_net_pay(config)
            gross_pay = CompensationService.calculate_gross_pay(config)
            total_deductions = CompensationService.calculate_total_deductions(
                config)

            # Build the "Payroll Result" (Thi will eventually be saved to OUR database)
            result = {
                "employee_id": employee.id,
                "full_name": f"{employee.lastName}, {employee.firstName}",
                "employee_number": employee.employeeId,
                "basic_salary": config.basicSalary,
                "gross_pay": gross_pay,
                "total_deductions": total_deductions,
                "net_pay": net_pay,
                "status": "Calculated"
            }

            payroll_results.append(result)
        return payroll_results
