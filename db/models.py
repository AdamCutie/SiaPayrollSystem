from datetime import datetime, timezone
from typing import List, Optional, Annotated
from pydantic import BaseModel, EmailStr, Field, ConfigDict, BeforeValidator
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
    department: Optional[str] = None

    # Financial Data (The values at the time of processing)
    basic_salary: float
    gross_pay: float
    net_pay: float
    
    # 🚀 Itemized Earnings
    housing_allowance: float = 0.0
    transport_allowance: float = 0.0
    meal_allowance: float = 0.0
    other_allowances: float = 0.0
    total_overtime: float = 0.0
    excess_days_pay: float = 0.0
    holiday_pay: float = 0.0
    special_day_pay: float = 0.0

    # 🚀 Itemized Deductions
    sss_deduction: float = 0.0
    philhealth_deduction: float = 0.0
    pagibig_deduction: float = 0.0
    withholding_tax: float = 0.0
    absence_deduction: float = 0.0
    total_loans: float = 0.0
    total_penalties: float = 0.0
    total_deductions: float
    undertime_deduction: float = 0.0

    total_late_hours: float = 0.0
    late_penalty_rate: float = 0.0
    late_penalty_items: List[dict] = Field(default_factory=list)
    worked_holiday_items: List[dict] = Field(default_factory=list)
    zero_net_reason: Optional[str] = None
    
    # 🚀 NEW: Attendance tracking for the Payslip (Figma: component_6.png)
    days_worked: int = 0
    days_present: int = 0
    days_absent: int = 0

    # Payroll Metadata
    pay_period_start: datetime
    pay_period_end: datetime
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "Pending" # Approved, Rejected, Pending
    remarks: Optional[str] = None # Added for Finance notes

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

class LeaveRequest(BaseModel):
    """Matches Figma: Leave.png table"""
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    employee_id: str
    employee_number: str
    full_name: str
    leave_type: str # Sick, Vacation, Maternity, etc.
    start_date: datetime
    end_date: datetime
    status: str = "Pending" # Approved, Rejected, Pending
    is_paid: bool = True

class Holiday(BaseModel):
    """Matches Figma: Holiday.png table"""
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    date: datetime
    name: str # e.g., "Chinese New Year"
    type: str # Regular Holiday, Special Non-Working Day

class AuthUser(BaseModel):
    """
    Payroll system credentials store.

    We treat the legacy HR database as read-only integration data.
    Passwords live in the payroll database to avoid mutating HR records.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    # Link back to the HR employee identity
    employee_id: str
    email: EmailStr

    password_hash: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActivityLog(BaseModel):
    """
    Local payroll activity log entry stored in OUR database.
    HR logs remain read-only in the HR database and are normalized at read time.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    source: str = "payroll"
    module: str
    action: str
    targetInfo: str = ""
    actorName: str = "System"
    actorEmail: Optional[str] = None
    actorEmployeeId: Optional[str] = None
    actorRole: Optional[str] = None
    visibility: str = "HR & Payroll"
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PayrollSchedule(BaseModel):
    """
    Stores the pre-calculated 24 cycles of the year.
    Used by the background runner to automate payroll.
    """
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    year: int
    cycle_name: str # e.g. "January - First Half"
    period_start: datetime
    period_end: datetime
    cutoff_date: datetime
    pay_date: datetime
    
    is_processed: bool = False
    automation_on: bool = False # The ON/OFF toggle
    processed_at: Optional[datetime] = None
    snapshot_count: int = 0

