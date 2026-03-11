from pydantic import BaseModel
from typing import Dict

class EmployeeStats(BaseModel):
    """Data for the 'TOTAL EMPLOYEES' card in Figma"""
    total: int
    regular: int
    provisional: int

class ApprovalStats(BaseModel):
    """Data for the 'APPROVAL STATUS' card in Figma"""
    requested: int
    approved: int
    pending: int
    rejected: int

class PayoutStats(BaseModel):
    """Data for the 'TOTAL PAYOUT' and 'DELAYED PAYOUT' cards in Figma"""
    total_payout: float
    delayed_payout: float
    average_salary: float

class DashboardOverview(BaseModel):
    """The master JSON for the Admin Overview page"""
    employees: EmployeeStats
    approvals: ApprovalStats
    payouts: PayoutStats
    departments: Dict[str, int]
