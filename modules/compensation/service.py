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
        days_present: int,
        holidays: List[object] = []
    ) -> dict:
        """
        STRICT LEGAL CALCULATOR (PH LABOR CODE)
        Uses a Standard 22-Day Monthly Divisor for accuracy.
        """
        # 0. Global Check: Total Absence Rule
        if days_present <= 0:
            return {
                "basic_salary": 0.0, "gross_pay": 0.0, "net_pay": 0.0,
                "housing_allowance": 0.0, "transport_allowance": 0.0, "meal_allowance": 0.0, "other_allowances": 0.0,
                "total_overtime": 0.0, "excess_days_pay": 0.0, "sss_deduction": 0.0, "philhealth_deduction": 0.0, "pagibig_deduction": 0.0,
                "withholding_tax": 0.0, "absence_deduction": 0.0, "total_loans": 0.0, "total_penalties": 0.0, "total_deductions": 0.0
            }

        # 1. The 'Sia Standard' Daily Rate (Monthly Salary / 22 Standard Workdays)
        standard_divisor = 22.0
        daily_rate = round(float(config.basicSalary) / standard_divisor, 2)
        
        # 2. Pro-rated Basic Salary for THIS period
        # Instead of paying the full month, we pay for the days in the period.
        period_basic_salary = round(daily_rate * expected_workdays, 2)

        # 3. Pro-rated Allowances
        attendance_ratio = min(1.0, days_present / max(1, expected_workdays))
        h_base = getattr(config, 'housingAllowance', 0) or 0
        t_base = getattr(config, 'transportAllowance', 0) or 0
        m_base = getattr(config, 'mealAllowance', 0) or 0
        o_base = getattr(config, 'otherAllowances', 0) or 0

        housing = round(float(h_base) * attendance_ratio, 2)
        transport = round(float(t_base) * attendance_ratio, 2)
        meal = round(float(m_base) * attendance_ratio, 2)
        other = round(float(o_base) * attendance_ratio, 2)
        
        total_allowances = housing + transport + meal + other

        # 4. Legal Holiday Premiums
        reg_holiday_pay = 0.0
        special_holiday_pay = 0.0
        
        for h in holidays:
            if h.type == "Regular Holiday":
                # worked? +100% premium
                if days_present >= expected_workdays:
                    reg_holiday_pay += daily_rate * 1.0
            elif h.type == "Special Non-Working Day":
                # worked? +30% premium
                if days_present >= expected_workdays:
                    special_holiday_pay += daily_rate * 0.3

        # 5. Overtime & Excess Days
        ot_coll = db["OvertimeRecords"]
        overtimes = await ot_coll.find({"employee_id": employee_id, "status": "Approved"}).to_list(None)
        
        # total_overtime now ONLY refers to the logs in the OT table
        total_overtime_logs = sum(o["total_pay"] for o in overtimes)

        excess_days = max(0, days_present - expected_workdays)
        excess_days_pay = round(daily_rate * excess_days, 2) 

        # 6. Deductions Logic
        sss = AgencyCalculator.calculate_sss(config.basicSalary)
        philhealth = AgencyCalculator.calculate_philhealth(config.basicSalary)
        pagibig = AgencyCalculator.calculate_pagibig(config.basicSalary)
        statutory_total = sss + philhealth + pagibig

        # 🚀 FIX: Define adjusted_expected BEFORE using it for absence deduction
        reg_holiday_count = sum(1 for h in holidays if h.type == "Regular Holiday")
        adjusted_expected = max(1, expected_workdays - reg_holiday_count)

        days_absent = max(0, adjusted_expected - days_present)
        absence_deduction = round(daily_rate * days_absent, 2)

        # 7. Final Gross & Net
        gross_pay = period_basic_salary + total_allowances + total_overtime_logs + excess_days_pay + reg_holiday_pay + special_holiday_pay
        
        taxable_income = max(0.0, gross_pay - statutory_total - absence_deduction)
        tax = AgencyCalculator.calculate_withholding_tax(taxable_income)

        total_loans = float(config.sssLoan or 0) + float(config.pagIbigLoan or 0) + float(config.companyLoan or 0)
        
        penalty_coll = db["PenaltyRecords"]
        penalties = await penalty_coll.find({"employee_id": employee_id, "status": "Approved"}).to_list(None)
        total_penalties = sum(p["amount"] for p in penalties)

        total_deductions = statutory_total + tax + total_loans + absence_deduction
        net_pay = gross_pay - (total_deductions + total_penalties)

        return {
            "basic_salary": period_basic_salary,
            "gross_pay": round(gross_pay, 2),
            "net_pay": max(0.0, round(net_pay, 2)),
            "housing_allowance": housing,
            "transport_allowance": transport,
            "meal_allowance": meal,
            "other_allowances": other,
            "total_overtime": round(total_overtime_logs, 2),
            "excess_days_pay": excess_days_pay,
            "holiday_pay": round(reg_holiday_pay, 2),
            "special_day_pay": round(special_holiday_pay, 2),
            "sss_deduction": sss,
            "philhealth_deduction": philhealth,
            "pagibig_deduction": pagibig,
            "withholding_tax": tax,
            "absence_deduction": absence_deduction,
            "total_loans": total_loans,
            "total_penalties": total_penalties,
            "total_deductions": round(total_deductions, 2)
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
