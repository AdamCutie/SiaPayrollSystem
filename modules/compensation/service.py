from typing import List, Optional

from integrations.hr.schemas import HRPayrollConfigRead
from modules.agencies.service import AgencyCalculator


class CompensationService:
    """
    Service responsible for salary and payroll math.
    """

    @staticmethod
    def calculate_gross_pay(config: HRPayrollConfigRead) -> float:
        total_allowances = (
            config.housingAllowance
            + config.transportAllowance
            + config.mealAllowance
            + config.otherAllowances
        )
        return config.basicSalary + total_allowances

    @classmethod
    def calculate_total_deductions(cls, config: HRPayrollConfigRead) -> float:
        sss = AgencyCalculator.calculate_sss(config.basicSalary)
        philhealth = AgencyCalculator.calculate_philhealth(config.basicSalary)
        pagibig = AgencyCalculator.calculate_pagibig(config.basicSalary)

        statutory_total = sss + philhealth + pagibig
        gross = config.basicSalary + (
            config.housingAllowance
            + config.transportAllowance
            + config.mealAllowance
            + config.otherAllowances
        )
        taxable_income = max(0.0, gross - statutory_total)
        tax = AgencyCalculator.calculate_withholding_tax(taxable_income)
        loans = config.sssLoan + config.pagIbigLoan + config.companyLoan
        return statutory_total + tax + loans

    @classmethod
    async def calculate_payroll_breakdown(
        cls,
        config: HRPayrollConfigRead,
        expected_workdays: int,
        days_present: int,
        holidays: List[object] = [],
        hr_late_penalties: float = 0.0,
        overtime_pay: float = 0.0,
        attendance_dates: Optional[set] = None,
    ) -> dict:
        if days_present <= 0:
            return {
                "basic_salary": 0.0,
                "gross_pay": 0.0,
                "net_pay": 0.0,
                "housing_allowance": 0.0,
                "transport_allowance": 0.0,
                "meal_allowance": 0.0,
                "other_allowances": 0.0,
                "total_overtime": 0.0,
                "excess_days_pay": 0.0,
                "sss_deduction": 0.0,
                "philhealth_deduction": 0.0,
                "pagibig_deduction": 0.0,
                "withholding_tax": 0.0,
                "absence_deduction": 0.0,
                "days_absent": 0,
                "total_loans": 0.0,
                "total_penalties": 0.0,
                "total_deductions": 0.0,
            }

        standard_divisor = 26.0
        daily_rate = round(float(config.basicSalary) / standard_divisor, 2)
        period_basic_salary = round(daily_rate * expected_workdays, 2)

        attendance_ratio = min(1.0, days_present / max(1, expected_workdays))
        housing = round(float(getattr(config, "housingAllowance", 0) or 0) * attendance_ratio, 2)
        transport = round(float(getattr(config, "transportAllowance", 0) or 0) * attendance_ratio, 2)
        meal = round(float(getattr(config, "mealAllowance", 0) or 0) * attendance_ratio, 2)
        other = round(float(getattr(config, "otherAllowances", 0) or 0) * attendance_ratio, 2)
        total_allowances = housing + transport + meal + other

        reg_holiday_pay = 0.0
        special_holiday_pay = 0.0
        attendance_dates = attendance_dates or set()
        for holiday in holidays:
            holiday_day = holiday.date.date()
            if holiday.type == "Regular Holiday" and holiday_day in attendance_dates:
                reg_holiday_pay += daily_rate * 1.0
            elif holiday.type == "Special Non-Working Day" and holiday_day in attendance_dates:
                special_holiday_pay += daily_rate * 0.3

        total_overtime_logs = round(float(overtime_pay or 0), 2)
        excess_days = max(0, days_present - expected_workdays)
        excess_days_pay = round(daily_rate * excess_days, 2)

        sss = AgencyCalculator.calculate_sss(config.basicSalary)
        philhealth = AgencyCalculator.calculate_philhealth(config.basicSalary)
        pagibig = AgencyCalculator.calculate_pagibig(config.basicSalary)
        statutory_total = sss + philhealth + pagibig

        reg_holiday_count = sum(1 for holiday in holidays if holiday.type == "Regular Holiday")
        adjusted_expected = max(1, expected_workdays - reg_holiday_count)
        days_absent = max(0, adjusted_expected - days_present)
        absence_deduction = round(daily_rate * days_absent, 2)

        gross_pay = (
            period_basic_salary
            + total_allowances
            + total_overtime_logs
            + excess_days_pay
            + reg_holiday_pay
            + special_holiday_pay
        )
        taxable_income = max(0.0, gross_pay - statutory_total - absence_deduction)
        tax = AgencyCalculator.calculate_withholding_tax(taxable_income)
        total_loans = float(config.sssLoan or 0) + float(config.pagIbigLoan or 0) + float(config.companyLoan or 0)
        total_penalties = round(float(hr_late_penalties or 0), 2)
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
            "days_absent": days_absent,
            "total_loans": total_loans,
            "total_penalties": total_penalties,
            "total_deductions": round(total_deductions, 2),
        }

    @classmethod
    async def calculate_net_pay(cls, config: HRPayrollConfigRead, employee_id: str) -> float:
        gross = cls.calculate_gross_pay(config)
        deductions = cls.calculate_total_deductions(config)
        return max(0.0, round(gross - deductions, 2))
