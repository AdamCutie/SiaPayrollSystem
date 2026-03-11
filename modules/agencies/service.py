class AgencyCalculator:
    """
    Service to calculate mandatory government deductions 
    based on the Philippine law tables shown in Figma.
    """
    
    @staticmethod
    def calculate_philhealth(salary: float) -> float:
        """
        Implementation of the PhilHealth Figma table (5.5% rate).
        Ceiling is 50,000.
        """
        # Apply the 50,000 ceiling cap from Figma
        taxable_salary = min(salary, 50000.0)
        
        # Calculate 5.5% Total Contribution
        total_contribution = taxable_salary * 0.055
        
        # Employee pays exactly half (split between Employee/Employer)
        return round(total_contribution / 2, 2)

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
