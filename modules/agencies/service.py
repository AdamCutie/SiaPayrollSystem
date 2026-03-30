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
        Finds the SSS deduction based on Figma salary brackets.
        (Simplified logic for teaching purposes based on 50k ceiling).
        """
        if salary <= 10000:
            return 450.0 # Lowest bracket employee share
        elif salary <= 20000:
            return 900.0
        elif salary <= 30000:
            return 1350.0
        elif salary <= 40000:
            return 1800.0
        else:
            return 2250.0 # Cap for 50,000 salary ceiling

    @staticmethod
    def calculate_pagibig(salary: float) -> float:
        """
        Pag-IBIG (HDMF) Rules:
        - Monthly Compensation Ceiling: 10,000
        - Employee Share: 2% of basic salary
        - Maximum Employee Contribution: 200.00
        """
        basis = min(salary, 10000.0)
        return round(basis * 0.02, 2)
