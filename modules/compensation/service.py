from typing import Optional, List
from integrations.hr.schemas import HRPayrollConfigRead
from modules.agencies.service import AgencyCalculator
from core.database import db

class CompensationService:
    """
    Service responsible for all salary-related calculations.
    This is the 'Brain' of our payroll system.
    """

    @staticmethod
    def calculate_gross_pay(config: HRPayrollConfigRead) -> float:
        """
        Calculates the Gross Pay: Basic Salary + all Allowances.
        """
        total_allowances = (
            config.housingAllowance +
            config.transportAllowance +
            config.mealAllowance +
            config.otherAllowances
        )
        return config.basicSalary + total_allowances

    @classmethod
    def calculate_total_deductions(cls, config: HRPayrollConfigRead) -> float:
        """
        Calculates total deductions: Automatic Govt Deductions + Loans + Other.
        """
        sss = AgencyCalculator.calculate_sss(config.basicSalary)
        philhealth = AgencyCalculator.calculate_philhealth(config.basicSalary)

        statutory = (
            sss +
            philhealth +
            config.pagIbigContribution +
            config.withholdingTax
        )

        loans = (
            config.sssLoan +
            config.pagIbigLoan +
            config.companyLoan
        )

        return statutory + loans

    @classmethod
    async def calculate_net_pay(cls, config: HRPayrollConfigRead) -> float:
        """
        The final calculation: (Gross + Overtime) - (Deductions + Penalties).
        """
        gross = cls.calculate_gross_pay(config)
        deductions = cls.calculate_total_deductions(config)

        # 🚀 NEW: Add Overtime and Subtract Penalties from our DB (Figma requirement)
        penalty_coll = db["PenaltyRecords"]
        ot_coll = db["OvertimeRecords"]
        
        # Sum up all approved penalties for this employee
        penalties = await penalty_coll.find({"employee_id": config.employeeId, "status": "Approved"}).to_list(None)
        total_penalties = sum(p["amount"] for p in penalties)
        
        # Sum up all approved overtime for this employee
        overtimes = await ot_coll.find({"employee_id": config.employeeId, "status": "Approved"}).to_list(None)
        total_overtime = sum(o["total_pay"] for o in overtimes)

        # Net Pay calculation
        net_pay = (gross + total_overtime) - (deductions + total_penalties)
        
        return max(0.0, round(net_pay, 2))
