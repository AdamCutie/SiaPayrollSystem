from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class AttendanceDayStatus(BaseModel):
    """
    Status of an employee for a specific day.
    Used for the 31-day Monthly Attendance Sheet.
    """
    date: date
    status: str  # "Present", "Absent", "On Leave", "Holiday", "Weekend"
    log_id: Optional[str] = None
    remarks: Optional[str] = None

class MonthlyAttendanceSheet(BaseModel):
    """
    A full monthly view of an employee's attendance.
    Matches Figma: Calendar/Sheet logic.
    """
    employee_id: str
    employee_number: str
    full_name: str
    month: int
    year: int
    days: List[AttendanceDayStatus]
    present_count: int
    absent_count: int
    leave_count: int
