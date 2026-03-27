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
        BIR TRAIN Law Graduated Brackets (Monthly).
        Calculated AFTER SSS, PhilHealth, and Pag-IBIG are deducted.
        """
        if taxable_income <= 20833:
            return 0.0
        elif taxable_income <= 33333:
            # 20% of excess over 20,833
            return round((taxable_income - 20833) * 0.20, 2)
        elif taxable_income <= 66666:
            # 2,500 + 25% of excess over 33,333
            return round(2500 + (taxable_income - 33333) * 0.25, 2)
        elif taxable_income <= 166666:
            # 10,833.33 + 30% of excess over 66,666
            return round(10833.33 + (taxable_income - 66666) * 0.30, 2)
        elif taxable_income <= 666666:
            # 40,833.33 + 32% of excess over 166,666
            return round(40833.33 + (taxable_income - 166666) * 0.32, 2)
        else:
            # 200,833.33 + 35% of excess over 666,666
            return round(200833.33 + (taxable_income - 666666) * 0.35, 2)

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
