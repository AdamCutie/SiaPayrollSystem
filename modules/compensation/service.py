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
        Calculates total deductions following the legal sequence:
        1. Statutory Contributions (SSS, PhilHealth, Pag-IBIG)
        2. Taxable Income = Gross - Statutory
        3. Withholding Tax = BIR_Table(Taxable Income)
        """
        # 1. Government Contributions (Statutory)
        sss = AgencyCalculator.calculate_sss(config.basicSalary)
        philhealth = AgencyCalculator.calculate_philhealth(config.basicSalary)
        pagibig = AgencyCalculator.calculate_pagibig(config.basicSalary)

        statutory_total = sss + philhealth + pagibig

        # 2. Determine Taxable Income (Gross - Statutory Contributions)
        gross = config.basicSalary + (
            config.housingAllowance +
            config.transportAllowance +
            config.mealAllowance +
            config.otherAllowances
        )
        taxable_income = max(0.0, gross - statutory_total)

        # 3. Calculate Withholding Tax (TRAIN Law Graduated Brackets)
        tax = AgencyCalculator.calculate_withholding_tax(taxable_income)

        # 4. Total Deductions = Statutory + Tax + Loans
        loans = (
            config.sssLoan +
            config.pagIbigLoan +
            config.companyLoan
        )

        return statutory_total + tax + loans

    @classmethod
    async def calculate_payroll_breakdown(
        cls, 
        config: HRPayrollConfigRead, 
        employee_id: str,
        expected_workdays: int,
        days_present: int
    ) -> dict:
        """
        Calculates all itemized components of the payroll, 
        including automatic deductions for absences.
        """
        # 1. Pro-rated Earnings (Attendance-Based)
        # If they worked full expected workdays or more, they get 100% of allowance.
        attendance_ratio = min(1.0, days_present / max(1, expected_workdays))
        
        # Pull values from config, ensuring defaults to 0 if missing
        h_base = getattr(config, 'housingAllowance', 0) or 0
        t_base = getattr(config, 'transportAllowance', 0) or 0
        m_base = getattr(config, 'mealAllowance', 0) or 0
        o_base = getattr(config, 'otherAllowances', 0) or 0

        housing = round(float(h_base) * attendance_ratio, 2)
        transport = round(float(t_base) * attendance_ratio, 2)
        meal = round(float(m_base) * attendance_ratio, 2)
        other = round(float(o_base) * attendance_ratio, 2)
        
        pro_rated_allowances = housing + transport + meal + other
        gross_without_ot = float(config.basicSalary) + pro_rated_allowances

        # sum up overtime
        ot_coll = db["OvertimeRecords"]
        overtimes = await ot_coll.find({"employee_id": employee_id, "status": "Approved"}).to_list(None)
        total_overtime = sum(o["total_pay"] for o in overtimes)

        # 2. Statutory Deductions
        sss = AgencyCalculator.calculate_sss(config.basicSalary)
        philhealth = AgencyCalculator.calculate_philhealth(config.basicSalary)
        pagibig = AgencyCalculator.calculate_pagibig(config.basicSalary)
        statutory_total = sss + philhealth + pagibig

        # 3. Absence & Excess Days Logic
        # Daily rate = Basic / expected workdays in period
        daily_rate = config.basicSalary / max(1, expected_workdays)
        
        days_absent = max(0, expected_workdays - days_present)
        absence_deduction = round(daily_rate * days_absent, 2)
        
        # 🚀 NEW: Automatic pay for extra days (e.g., working 12d when 10d expected)
        excess_days = max(0, days_present - expected_workdays)
        # We pay at a premium (e.g., 1.3x) or standard 1.0x for rest days
        excess_days_pay = round(daily_rate * excess_days * 1.0, 2) 

        # 4. Taxable Income & Withholding Tax
        # Taxable income includes (Gross + OT + Excess Pay) - Statutory - Absences
        taxable_income = max(0.0, (gross_without_ot + total_overtime + excess_days_pay) - statutory_total - absence_deduction)
        tax = AgencyCalculator.calculate_withholding_tax(taxable_income)

        # 5. Other Deductions (Loans & Penalties)
        total_loans = config.sssLoan + config.pagIbigLoan + config.companyLoan
        
        penalty_coll = db["PenaltyRecords"]
        penalties = await penalty_coll.find({"employee_id": employee_id, "status": "Approved"}).to_list(None)
        total_penalties = sum(p["amount"] for p in penalties)

        total_deductions = statutory_total + tax + total_loans + absence_deduction

        # 6. Final Net Pay (Include Excess Days Pay)
        net_pay = (gross_without_ot + total_overtime + excess_days_pay) - (total_deductions + total_penalties)

        return {
            "basic_salary": config.basicSalary,
            "gross_pay": gross_without_ot + total_overtime + excess_days_pay,
            "net_pay": max(0.0, round(net_pay, 2)),
            "housing_allowance": housing,
            "transport_allowance": transport,
            "meal_allowance": meal,
            "other_allowances": other,
            "total_overtime": total_overtime + excess_days_pay, # Merge for simplicity or keep separate
            "sss_deduction": sss,
            "philhealth_deduction": philhealth,
            "pagibig_deduction": pagibig,
            "withholding_tax": tax,
            "absence_deduction": absence_deduction,
            "total_loans": total_loans,
            "total_penalties": total_penalties,
            "total_deductions": total_deductions
        }

    @classmethod
    async def calculate_net_pay(cls, config: HRPayrollConfigRead, employee_id: str) -> float:
        """
        The final calculation: (Gross + Overtime) - (Deductions + Penalties).
        """
        gross = cls.calculate_gross_pay(config)
        deductions = cls.calculate_total_deductions(config)

        # 🚀 NEW: Add Overtime and Subtract Penalties from our DB (Figma requirement)
        penalty_coll = db["PenaltyRecords"]
        ot_coll = db["OvertimeRecords"]
        
        # Sum up all approved penalties for this employee
        penalties = await penalty_coll.find({"employee_id": employee_id, "status": "Approved"}).to_list(None)
        total_penalties = sum(p["amount"] for p in penalties)
        
        # Sum up all approved overtime for this employee
        overtimes = await ot_coll.find({"employee_id": employee_id, "status": "Approved"}).to_list(None)
        total_overtime = sum(o["total_pay"] for o in overtimes)

        # Net Pay calculation
        net_pay = (gross + total_overtime) - (deductions + total_penalties)
        
        return max(0.0, round(net_pay, 2))
