from datetime import datetime, timezone
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from bson import ObjectId

# Simple V2 Validator to handle MongoDB ObjectIds
PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]

class PayrollSnapshot(BaseModel):
    """
    The 'Receipt' of a payroll calculation.
    Stored in OUR new database (not the legacy HR one).
    """
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    # Link & Identifiers
    employee_id: str  # The original MongoDB _id from the HR system
    employee_number: str  # e.g., "23-2450"
    full_name: str

    # Financial Data (The values at the time of processing)
    basic_salary: float
    gross_pay: float
    total_deductions: float
    net_pay: float

    # Payroll Metadata
    pay_period_start: datetime
    pay_period_end: datetime
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "Completed"

class AttendanceLog(BaseModel):
    """
    Model for the Employee Work Log (Figma: adminDashboardPage.png bottom table).
    """
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    employee_id: str
    employee_number: str
    full_name: str
    department: str
    position: str
    date: datetime
    duration_hours: float
    status: str = "Pending" # Approved, Pending, Rejected
