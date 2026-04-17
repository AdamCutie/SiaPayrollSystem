class AgencyCalculator:
    """
    Service to calculate mandatory government deductions 
    based on the Philippine law (TRAIN Law & PhilHealth 2026).
    """
    
    @staticmethod
    def calculate_philhealth(salary: float) -> float:
        """
        PhilHealth 2026 Rules:
        - 5% Total Contribution Rate (Split 50/50)
        - Employee Share: 2.5%
        - Floor: 10,000 | Ceiling: 100,000
        """
        # Apply 10k floor and 100k ceiling
        basis = max(10000.0, min(salary, 100000.0))
        
        # Calculate 2.5% Employee Share
        return round(basis * 0.025, 2)

    @staticmethod
    def calculate_withholding_tax(taxable_income: float) -> float:
        """
        BIR TRAIN Law graduated brackets for semi-monthly payroll.
        Calculated after SSS, PhilHealth, and Pag-IBIG are deducted.
        """
        if taxable_income <= 10417:
            return 0.0
        elif taxable_income <= 16667:
            return round((taxable_income - 10417) * 0.20, 2)
        elif taxable_income <= 33333:
            return round(1250 + (taxable_income - 16667) * 0.25, 2)
        elif taxable_income <= 83333:
            return round(5416.67 + (taxable_income - 33333) * 0.30, 2)
        elif taxable_income <= 333333:
            return round(20416.67 + (taxable_income - 83333) * 0.32, 2)
        else:
            return round(100416.67 + (taxable_income - 333333) * 0.35, 2)

    @staticmethod
    def calculate_sss(salary: float) -> float:
        """
        Returns the monthly employee-paid SSS deduction for employed members
        under the January 2025 schedule.
        """
        breakdown = AgencyCalculator.calculate_sss_breakdown(salary)
        return breakdown["employee_total"]

    @staticmethod
    def calculate_sss_breakdown(salary: float) -> dict[str, float]:
        """
        Computes the employed-member SSS breakdown effective January 1, 2025.

        Rules:
        - Compensation below 5,250 maps to 5,000 MSC.
        - Compensation from 5,250 to 34,749.99 maps to MSC in 500 increments.
        - Compensation from 34,750 and above maps to 35,000 MSC.
        - Regular SS applies up to 20,000 MSC and is split 10% ER / 5% EE.
        - MPF applies on MSC above 20,000 up to 35,000 and is also split 10% ER / 5% EE.
        - EC is employer-only: 10 pesos for MSC 14,500 and below, otherwise 30 pesos.
        """
        salary = max(0.0, float(salary or 0.0))

        if salary < 5250.0:
            monthly_salary_credit = 5000.0
        elif salary >= 34750.0:
            monthly_salary_credit = 35000.0
        else:
            monthly_salary_credit = 5500.0 + (int((salary - 5250.0) // 500.0) * 500.0)

        regular_msc = min(monthly_salary_credit, 20000.0)
        mpf_msc = max(monthly_salary_credit - 20000.0, 0.0)

        employee_share = round(regular_msc * 0.05, 2)
        employer_share = round(regular_msc * 0.10, 2)
        mpf_employee_share = round(mpf_msc * 0.05, 2)
        mpf_employer_share = round(mpf_msc * 0.10, 2)
        ec_employer = 10.0 if monthly_salary_credit <= 14500.0 else 30.0

        return {
            "monthly_salary_credit": monthly_salary_credit,
            "regular_msc": regular_msc,
            "mpf_msc": mpf_msc,
            "employee_share": employee_share,
            "employer_share": employer_share,
            "mpf_employee_share": mpf_employee_share,
            "mpf_employer_share": mpf_employer_share,
            "employee_total": round(employee_share + mpf_employee_share, 2),
            "employer_total": round(employer_share + mpf_employer_share + ec_employer, 2),
            "regular_total": round(employee_share + employer_share, 2),
            "mpf_total": round(mpf_employee_share + mpf_employer_share, 2),
            "ec_employer": ec_employer,
            "overall_total": round(
                employee_share + employer_share + mpf_employee_share + mpf_employer_share + ec_employer,
                2,
            ),
        }

    @staticmethod
    def calculate_pagibig(salary: float) -> float:
        """
        Pag-IBIG (HDMF) Rules:
        - Monthly compensation base is capped at 5,000
        - Employee share is 1% for compensation up to 1,500
        - Employee share is 2% for compensation above 1,500
        - Maximum employee contribution is 100.00
        """
        breakdown = AgencyCalculator.calculate_pagibig_breakdown(salary)
        return breakdown["employee_share"]

    @staticmethod
    def calculate_pagibig_breakdown(salary: float) -> dict[str, float]:
        """
        Computes Pag-IBIG contribution shares for employed members.
        """
        salary = max(0.0, float(salary or 0.0))
        basis = min(salary, 5000.0)
        employee_rate = 0.01 if salary <= 1500.0 else 0.02
        employee_share = round(basis * employee_rate, 2)
        employer_share = round(basis * 0.02, 2)
        return {
            "basis": basis,
            "employee_rate": employee_rate,
            "employee_share": employee_share,
            "employer_share": employer_share,
            "overall_total": round(employee_share + employer_share, 2),
        }
