from typing import Optional
from integrations.hr.schemas import HRPayrollConfigRead
from modules.agencies.service import AgencyCalculator


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
        # Sum up all monthly allowances
        total_allowances = (
            config.housingAllowance +
            config.transportAllowance +
            config.mealAllowance +
            config.otherAllowances
        )

        # Add Basic Salary to get the Gross Pay
        return config.basicSalary + total_allowances

    @classmethod
    def calculate_total_deductions(cls, config: HRPayrollConfigRead) -> float:
        """
        Calculates total deductions: Automatic Govt Deductions + Loans + Other.
        """
        # 🚀 NEW: Automatic Government Deductions from Figma Tables
        sss = AgencyCalculator.calculate_sss(config.basicSalary)
        philhealth = AgencyCalculator.calculate_philhealth(config.basicSalary)

        # Government Mandatory Deductions (SSS & PhilHealth are now automatic)
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

        # combine everything
        return statutory + loans

    @classmethod
    def calculate_net_pay(cls, config: HRPayrollConfigRead) -> float:
        """
        The final calculation: Gross Pay minus Total Deductions.
        """
        gross = cls.calculate_gross_pay(config)
        deductions = cls.calculate_total_deductions(config)

        # Net Pay is what the employee actually takes home
        net_pay = gross - deductions
        # Ensure we never return a negative number
        return max(0.0, round(net_pay, 2))
