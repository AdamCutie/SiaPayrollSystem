from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import require_admin
from core.database import db
from integrations.hr.adapter import get_hr_attendance_list, get_employee_by_id, get_hr_leaves_list
from db.models import PenaltyRecord, OvertimeRecord, Holiday
from .schemas import MonthlyAttendanceSheet, AttendanceDayStatus
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timedelta, date
import calendar

router = APIRouter(
    prefix="/attendance",
    tags=["Attendance & Work Log"],
    dependencies=[Depends(require_admin)],
)

@router.get("/logs")
async def get_all_work_logs(
    employee_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None), # today, yesterday, lastweek
    month: Optional[int] = Query(None) # 1-12
):
    """
    Fetches real-time work logs from the Legacy HR System (Source of Truth).
    Returns raw data for UI viewing.
    """
    try:
        start_date = None
        end_date = None
        
        now = datetime.now()
        
        if month:
            # Filter by specific month of the current year
            start_date = datetime(now.year, month, 1, 0, 0, 0)
            # Find last day of month
            if month == 12:
                end_date = datetime(now.year, 12, 31, 23, 59, 59)
            else:
                end_date = datetime(now.year, month + 1, 1) - timedelta(seconds=1)
        elif period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "yesterday":
            yesterday = now - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "lastweek":
            # Last 7 days
            start_date = now - timedelta(days=7)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            
        return await get_hr_attendance_list(employee_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch HR work logs: {str(e)}")

@router.get("/sheet/{employee_id}", response_model=MonthlyAttendanceSheet)
async def get_monthly_attendance_sheet(
    employee_id: str,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...)
):
    """
    Generates a 31-day (or 28/30) attendance sheet for a specific employee.
    This merges logs, leaves, and holidays to show the full status of every day.
    """
    # 1. Verify employee exists
    emp = await get_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # 2. Get Date Range for the month
    _, last_day = calendar.monthrange(year, month)
    start_dt = datetime(year, month, 1)
    end_dt = datetime(year, month, last_day, 23, 59, 59)

    # 3. Fetch all relevant data for the month
    logs = await get_hr_attendance_list(emp.employeeId, start_dt, end_dt)
    leaves = await get_hr_leaves_list(emp.employeeId, start_dt, end_dt)
    
    holidays_coll = db["Holidays"]
    cursor = holidays_coll.find({"date": {"$gte": start_dt, "$lte": end_dt}})
    holidays = [Holiday(**doc) async for doc in cursor]

    # Map logs/leaves by date for O(1) lookup
    log_map = {doc["date"].date(): doc for doc in logs if "date" in doc}
    # Note: Leaves can span multiple days
    leave_dates = {}
    for l in leaves:
        curr = l["startDate"].date()
        while curr <= l["endDate"].date():
            leave_dates[curr] = l
            curr += timedelta(days=1)
    
    holiday_dates = {h.date.date(): h.name for h in holidays}

    # 4. Generate the 1-31 List
    days: List[AttendanceDayStatus] = []
    p_count, a_count, l_count = 0, 0, 0

    for day_num in range(1, last_day + 1):
        curr_date = date(year, month, day_num)
        status = "Absent"
        log_id = None
        remarks = None

        if curr_date in log_map:
            status = "Present"
            log_id = str(log_map[curr_date]["_id"])
            p_count += 1
        elif curr_date in leave_dates:
            status = "On Leave"
            remarks = leave_dates[curr_date].get("leave_type", "Leave")
            l_count += 1
        elif curr_date in holiday_dates:
            status = "Holiday"
            remarks = holiday_dates[curr_date]
        elif curr_date.weekday() >= 5: # Saturday/Sunday
            status = "Weekend"
        else:
            a_count += 1

        days.append(AttendanceDayStatus(
            date=curr_date,
            status=status,
            log_id=log_id,
            remarks=remarks
        ))

    return MonthlyAttendanceSheet(
        employee_id=employee_id,
        employee_number=emp.employeeId,
        full_name=f"{emp.lastName}, {emp.firstName}",
        month=month,
        year=year,
        days=days,
        present_count=p_count,
        absent_count=a_count,
        leave_count=l_count
    )

@router.get("/penalties", response_model=List[PenaltyRecord])
async def get_penalty_logs():
    """Matches Figma: Penalize.png table"""
    collection = db["PenaltyRecords"]
    cursor = collection.find().sort("date", -1)
    return [PenaltyRecord(**doc) async for doc in cursor]

@router.get("/overtime", response_model=List[OvertimeRecord])
async def get_overtime_logs():
    """Matches Figma: Overtime.png table"""
    collection = db["OvertimeRecords"]
    cursor = collection.find().sort("date", -1)
    return [OvertimeRecord(**doc) async for doc in cursor]
