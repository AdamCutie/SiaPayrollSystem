from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth import require_admin
from core.database import db
from db.models import PenaltyRecord, OvertimeRecord, Holiday, PyObjectId
from integrations.hr.adapter import get_hr_attendance_list, get_employee_by_id, get_hr_leaves_list
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
    Uses the real system clock for time-based filtering.
    """
    try:
        start_date = None
        end_date = None
        now_ref = datetime.now()
        
        if month:
            start_date = datetime(now_ref.year, month, 1, 0, 0, 0)
            if month == 12:
                end_date = datetime(now_ref.year, 12, 31, 23, 59, 59)
            else:
                end_date = datetime(now_ref.year, month + 1, 1) - timedelta(seconds=1)
        elif period == "today":
            start_date = now_ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "yesterday":
            yesterday = now_ref - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "lastweek":
            start_date = now_ref - timedelta(days=7)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
            
        emp_number = None
        if employee_id:
            emp = await get_employee_by_id(employee_id)
            if emp:
                emp_number = emp.employeeId

        return await get_hr_attendance_list(emp_number, start_date, end_date)
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
    # Pass emp.employeeId (the human number like 26-2214) to the adapter
    logs = await get_hr_attendance_list(emp.employeeId, start_dt, end_dt)
    leaves = await get_hr_leaves_list(emp.employeeId, start_dt, end_dt)
    
    # 🛡️ FIX: Ensure we fetch ALL holidays for the selected month by using date-only comparison logic
    holidays_coll = db["Holidays"]
    # Create start and end of month at absolute boundaries
    search_start = datetime(year, month, 1, 0, 0, 0)
    search_end = datetime(year, month, last_day, 23, 59, 59)
    
    cursor = holidays_coll.find({"date": {"$gte": search_start, "$lte": search_end}})
    holidays = [Holiday(**doc) async for doc in cursor]

    # Helper to parse dates from HR which might be strings
    def parse_hr_date(d_val):
        if isinstance(d_val, datetime): return d_val.date()
        if isinstance(d_val, str): 
            # Handle ISO format like 2026-04-04T00:00:00 or just 2026-04-04
            return datetime.fromisoformat(d_val.split('T')[0]).date()
        return d_val

    # Map logs/leaves by date for O(1) lookup
    log_map = {parse_hr_date(doc.get("date")): doc for doc in logs if doc.get("date")}
    
    leave_dates = {}
    for l in leaves:
        s_date = parse_hr_date(l.get("startDate"))
        e_date = parse_hr_date(l.get("endDate"))
        if s_date and e_date:
            curr = s_date
            while curr <= e_date:
                leave_dates[curr] = l
                curr += timedelta(days=1)
    
    # Map holidays by date, allowing for multiple holidays on the same day
    holiday_map = {}
    for h in holidays:
        d = parse_hr_date(h.date)
        if d not in holiday_map:
            holiday_map[d] = []
        holiday_map[d].append(f"{h.name} ({h.type})")
    
    # 4. Generate the 1-31 List
    days: List[AttendanceDayStatus] = []
    p_count, a_count, l_count = 0, 0, 0

    for day_num in range(1, last_day + 1):
        curr_date = date(year, month, day_num)
        status = "Absent"
        log_id = None
        remarks = None

        # 🚀 PRIORITY 1: HOLIDAY DETECTION
        if curr_date in holiday_map:
            status = "Holiday"
            remarks = ", ".join(holiday_map[curr_date])
            # Check if they also worked on this holiday
            if curr_date in log_map:
                log_id = str(log_map[curr_date].get("_id"))
                remarks += " (Worked)"
                p_count += 1
        
        # 🚀 PRIORITY 2: LOGS (PRESENT)
        elif curr_date in log_map:
            status = "Present"
            log_id = str(log_map[curr_date].get("_id"))
            p_count += 1
            
        # 🚀 PRIORITY 3: LEAVES
        elif curr_date in leave_dates:
            status = "On Leave"
            remarks = leave_dates[curr_date].get("leave_type", "Leave")
            l_count += 1
            
        # 🚀 PRIORITY 4: WEEKENDS
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

@router.patch("/overtime/{record_id}/approve")
async def approve_overtime(record_id: str, _: object = Depends(require_admin)):
    """Approves an overtime record in OUR database so it gets paid."""
    collection = db["OvertimeRecords"]
    result = await collection.update_one(
        {"_id": PyObjectId(record_id)},
        {"$set": {"status": "Approved", "updated_at": datetime.now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Overtime approved"}

@router.patch("/overtime/{record_id}/reject")
async def reject_overtime(record_id: str, _: object = Depends(require_admin)):
    """Rejects an overtime record."""
    collection = db["OvertimeRecords"]
    result = await collection.update_one(
        {"_id": PyObjectId(record_id)},
        {"$set": {"status": "Rejected", "updated_at": datetime.now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Overtime rejected"}

@router.patch("/penalties/{record_id}/approve")
async def waive_penalty(record_id: str, _: object = Depends(require_admin)):
    """Waives a penalty (marks as Waived so it is NOT deducted)."""
    collection = db["PenaltyRecords"]
    result = await collection.update_one(
        {"_id": PyObjectId(record_id)},
        {"$set": {"status": "Waived", "updated_at": datetime.now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Penalty waived"}

@router.patch("/penalties/{record_id}/reject")
async def apply_penalty(record_id: str, _: object = Depends(require_admin)):
    """Applies a penalty (marks as Approved so it IS deducted)."""
    collection = db["PenaltyRecords"]
    result = await collection.update_one(
        {"_id": PyObjectId(record_id)},
        {"$set": {"status": "Approved", "updated_at": datetime.now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Penalty applied"}

@router.get("/overtime", response_model=List[OvertimeRecord])
async def get_overtime_logs():
    """Matches Figma: Overtime.png table. Enriched with names."""
    collection = db["OvertimeRecords"]
    cursor = collection.find().sort("date", -1)
    records = [OvertimeRecord(**doc) async for doc in cursor]
    
    # Enrich with names from HR
    from integrations.hr.adapter import get_employee_by_id
    for r in records:
        emp = await get_employee_by_id(r.employee_id)
        if emp:
            r.full_name = f"{emp.lastName}, {emp.firstName}"
    return records

@router.get("/penalties", response_model=List[PenaltyRecord])
async def get_penalty_logs():
    """Enriched with names."""
    collection = db["PenaltyRecords"]
    cursor = collection.find().sort("date", -1)
    records = [PenaltyRecord(**doc) async for doc in cursor]
    
    from integrations.hr.adapter import get_employee_by_id
    for r in records:
        emp = await get_employee_by_id(r.employee_id)
        if emp:
            r.full_name = f"{emp.lastName}, {emp.firstName}"
    return records
