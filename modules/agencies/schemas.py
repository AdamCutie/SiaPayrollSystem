from pydantic import BaseModel
from typing import List

class PhilHealthRate(BaseModel):
    """Matches the PhilHealth Figma table (5.5% rate)"""
    monthly_salary: float
    total_contribution: float
    employee_share: float
    employer_share: float

class SSSBracket(BaseModel):
    """Matches the SSS Figma table for salary ranges"""
    min_salary: float
    max_salary: float
    monthly_salary_credit: float
    employee_share: float
    employer_share: float
