from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth import require_admin
from core.database import db
from db.models import Holiday
from integrations.hr.adapter import (
    get_all_active_employees,
    get_synced_employee_by_id,
    get_synced_employee_payroll_config,
    get_synced_attendance_list,
    get_synced_leave_list,
    get_synced_overtime_requests,
    get_synced_undertime_records,
)
from .schemas import MonthlyAttendanceSheet, AttendanceDayStatus
from typing import List, Optional
from datetime import datetime, timedelta, date
import calendar
import math

router = APIRouter(
    prefix="/attendance",
    tags=["Attendance & Work Log"],
    dependencies=[Depends(require_admin)],
)

@router.get("/logs")
async def get_all_work_logs(
    employee_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None), # today, yesterday, lastweek
    month: Optional[int] = Query(None), # 1-12
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """
    Fetches attendance logs from the synced HR mirror in our payroll database.
    """
    try:
        now_ref = datetime.now()
        
        if start_date and end_date:
            if end_date.hour == 0 and end_date.minute == 0:
                end_date = end_date.replace(hour=23, minute=59, second=59)
        elif month:
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
        elif period == "all":
            start_date = None
            end_date = None
            
        emp_number = None
        if employee_id:
            emp = await get_synced_employee_by_id(employee_id)
            emp_number = emp.employeeId if emp else employee_id

        if not (start_date and end_date) and period != "all":
            end_date = now_ref
            start_date = end_date - timedelta(days=30)

        return await get_synced_attendance_list(emp_number, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch synced attendance logs: {str(e)}")

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
    emp = await get_synced_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    _, last_day = calendar.monthrange(year, month)
    start_dt = datetime(year, month, 1)
    end_dt = datetime(year, month, last_day, 23, 59, 59)

    logs = await get_synced_attendance_list(emp.employeeId, start_dt, end_dt)
    leaves = await get_synced_leave_list(emp.employeeId, start_dt, end_dt, approved_only=True)
    
    holidays_coll = db["Holidays"]
    cursor = holidays_coll.find({"date": {"$gte": start_dt, "$lte": end_dt}})
    holidays = [Holiday(**doc) async for doc in cursor]

    def parse_hr_date(d_val):
        if isinstance(d_val, datetime): return d_val.date()
        if isinstance(d_val, str): 
            return datetime.fromisoformat(d_val.split('T')[0]).date()
        return d_val

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
    
    holiday_map = {}
    for h in holidays:
        d = parse_hr_date(h.date)
        if d not in holiday_map:
            holiday_map[d] = []
        holiday_map[d].append(f"{h.name} ({h.type})")
    
    days: List[AttendanceDayStatus] = []
    p_count, a_count, l_count = 0, 0, 0

    for day_num in range(1, last_day + 1):
        curr_date = date(year, month, day_num)
        status = "Absent"
        log_id = None
        remarks = None

        if curr_date in holiday_map:
            status = "Holiday"
            remarks = ", ".join(holiday_map[curr_date])
            if curr_date in log_map:
                log_id = str(log_map[curr_date].get("_id"))
                remarks += " (Worked)"
                p_count += 1
        elif curr_date in log_map:
            status = "Present"
            log_id = str(log_map[curr_date].get("_id"))
            p_count += 1
        elif curr_date in leave_dates:
            status = "On Leave"
            remarks = leave_dates[curr_date].get("leave_type") or leave_dates[curr_date].get("leaveType", "Leave")
            l_count += 1
        elif curr_date.weekday() == 6: # Sunday
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

def parse_ot_hours(time_str: str) -> float:
    try:
        if not time_str: return 0.0
        parts = time_str.split(':')
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2])
        return round(h + (m / 60.0) + (s / 3600.0), 2)
    except:
        return 0.0

def parse_late_duration_to_hours(value, field_name: str = "") -> float:
    if value in (None, "", 0, 0.0, "0", "00:00", "00:00:00"):
        return 0.0
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0: return 0.0
        if "minute" in field_name.casefold(): return round(numeric / 60.0, 2)
        return round(numeric, 2)
    if isinstance(value, str):
        raw = value.strip()
        if not raw: return 0.0
        if ":" in raw:
            parts = raw.split(":")
            try:
                h = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 else 0
                s = int(parts[2]) if len(parts) > 2 else 0
                total_seconds = (h * 3600) + (m * 60) + s
                return round(total_seconds / 3600.0, 2)
            except: return 0.0
        try:
            numeric = float(raw)
            if numeric <= 0: return 0.0
            if "minute" in field_name.casefold(): return round(numeric / 60.0, 2)
            return round(numeric, 2)
        except: return 0.0
    return 0.0

def extract_late_info(doc: dict) -> Optional[dict]:
    for field_name in ("lateTime", "lateHours", "lateMinutes", "late", "tardiness"):
        if field_name not in doc: continue
        late_hours = parse_late_duration_to_hours(doc.get(field_name), field_name)
        if late_hours > 0:
            return {"field_name": field_name, "raw_value": doc.get(field_name), "late_hours": late_hours}
    return None

@router.get("/overtime")
async def get_overtime_requests(
    employee_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    try:
        now_ref = datetime.now()
        if start_date and end_date:
            if end_date.hour == 0 and end_date.minute == 0: end_date = end_date.replace(hour=23, minute=59, second=59)
        elif month:
            start_date = datetime(now_ref.year, month, 1)
            end_date = (datetime(now_ref.year, month + 1, 1) if month < 12 else datetime(now_ref.year + 1, 1, 1)) - timedelta(seconds=1)
        elif period == "today":
            start_date = now_ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "yesterday":
            yesterday = now_ref - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "lastweek":
            start_date = (now_ref - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "all":
            start_date, end_date = None, None

        emp_number = None
        if employee_id:
            emp = await get_synced_employee_by_id(employee_id)
            emp_number = emp.employeeId if emp else employee_id

        hr_requests = await get_synced_overtime_requests(employee_number=emp_number, start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch overtime: {str(e)}")
    
    enriched = []
    
    # 🚀 OPTIMIZATION: Fetch employees and cache them OUTSIDE the loop
    employees = await get_all_active_employees()
    employee_by_id = {str(emp.employeeId).strip(): emp for emp in employees}
    config_cache = {}

    import re
    for req in hr_requests:
        req_status = req.get("status") or "Pending"
        if status:
            check_status = req_status
            if status.lower() == "rejected" and req_status.lower() in ["declined", "denied"]:
                check_status = "rejected"
            if not re.search(f"^{status}$", check_status, re.IGNORECASE):
                continue

        req["hours"] = parse_ot_hours(req.get("overtimeWorked", "0:0:0"))
        req["full_name"] = req.get("fullName")
        try:
            emp_no = str(req.get("employeeId", "")).strip()
            emp = employee_by_id.get(emp_no)
            if emp:
                if emp.id not in config_cache:
                    config_cache[emp.id] = await get_synced_employee_payroll_config(emp.id, emp.employeeId, f"{emp.lastName}, {emp.firstName}")
                config = config_cache[emp.id]
                if config:
                    hourly_rate = (float(config.basicSalary) / 26.0) / 8.0
                    req["rate_per_hour"] = round(hourly_rate * 1.25, 2)
                    req["total_pay"] = round(req["hours"] * req["rate_per_hour"], 2)
        except Exception as e: 
            print(f"Error calculating overtime for {req.get('employeeId')}: {e}")
        enriched.append(req)
    return enriched

@router.get("/penalties")
async def get_penalty_logs(
    employee_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    try:
        now_ref = datetime.now()
        if start_date and end_date:
            if end_date.hour == 0 and end_date.minute == 0: end_date = end_date.replace(hour=23, minute=59, second=59)
        elif month:
            start_date = datetime(now_ref.year, month, 1)
            end_date = (datetime(now_ref.year, month + 1, 1) if month < 12 else datetime(now_ref.year + 1, 1, 1)) - timedelta(seconds=1)
        elif period == "today":
            start_date = now_ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "yesterday":
            y = now_ref - timedelta(days=1)
            start_date = y.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = y.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "lastweek":
            start_date = (now_ref - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "all":
            start_date, end_date = None, None

        emp_number = None
        if employee_id:
            emp = await get_synced_employee_by_id(employee_id)
            emp_number = emp.employeeId if emp else employee_id

        if not (start_date and end_date) and period != "all":
            end_date = now_ref
            start_date = end_date - timedelta(days=30)

        logs = await get_synced_attendance_list(emp_number, start_date, end_date)
        employees = await get_all_active_employees()
        employee_by_number = {str(emp.employeeId).strip(): emp for emp in employees}
        config_cache = {}
        records = []

        import re
        for log in logs:
            late_info = extract_late_info(log)
            if not late_info: continue
            
            log_status = log.get("status") or "Detected"
            if status:
                check_status = log_status
                if status.lower() == "rejected" and log_status.lower() in ["declined", "denied"]:
                    check_status = "rejected"
                if not re.search(f"^{status}$", check_status, re.IGNORECASE):
                    continue

            emp_no = str(log.get("employeeId", "")).strip()
            hr_emp = employee_by_number.get(emp_no)
            full_name = log.get("employeeName") or f"Unknown ({emp_no})"
            emp_hr_id, late_rate = emp_no, 0.0
            if hr_emp:
                emp_hr_id = hr_emp.id
                full_name = f"{hr_emp.lastName}, {hr_emp.firstName}"
                if hr_emp.id not in config_cache:
                    config_cache[hr_emp.id] = await get_synced_employee_payroll_config(hr_emp.id, hr_emp.employeeId, full_name)
                config = config_cache[hr_emp.id]
                if config: late_rate = float(getattr(config, "latePenaltyRate", 0) or 0)

            records.append({
                "_id": str(log.get("_id")), "employee_id": emp_hr_id, "employee_number": emp_no,
                "full_name": full_name, "date": log.get("date"), "penalty_type": "Late",
                "reason": f"Automatic payroll deduction from HR lateness ({late_info['field_name']})",
                "late_time": str(late_info["raw_value"]), "late_hours": late_info["late_hours"],
                "rate_per_hour": round(late_rate, 2), "amount": round(late_info["late_hours"] * late_rate, 2),
                "status": log_status, "source": "HR Attendance / Auto Deducted in Payroll",
            })
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch penalties: {str(e)}")

@router.get("/undertime")
async def get_undertime_records(
    employee_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    try:
        now_ref = datetime.now()
        if start_date and end_date:
            if end_date.hour == 0 and end_date.minute == 0: end_date = end_date.replace(hour=23, minute=59, second=59)
        elif period == "today":
            start_date = now_ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "yesterday":
            y = now_ref - timedelta(days=1)
            start_date = y.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = y.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "lastweek":
            start_date = (now_ref - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "all":
            start_date, end_date = None, None

        emp_number = None
        if employee_id:
            emp = await get_synced_employee_by_id(employee_id)
            emp_number = emp.employeeId if emp else employee_id

        if not (start_date and end_date) and period != "all":
            end_date = now_ref
            start_date = end_date - timedelta(days=30)

        hr_records = await get_synced_undertime_records(employee_number=emp_number, start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch undertime: {str(e)}")
    
    enriched = []

    # 🚀 OPTIMIZATION: Fetch employees and cache them OUTSIDE the loop
    employees = await get_all_active_employees()
    employee_by_id = {str(emp.employeeId).strip(): emp for emp in employees}
    config_cache = {}

    import re
    for rec in hr_records:
        rec_status = rec.get("status") or "Pending"
        if status:
            check_status = rec_status
            if status.lower() == "rejected" and rec_status.lower() in ["declined", "denied"]:
                check_status = "rejected"
            if not re.search(f"^{status}$", check_status, re.IGNORECASE):
                continue

        # Use 'hoursUndertime' from HR payload
        rec["hours"] = round(float(rec.get("hoursUndertime", 0)), 2)
        rec["full_name"] = rec.get("fullName")
        try:
            # Use 'hourlyRate' from HR payload if available, else calculate
            payload_rate = float(rec.get("hourlyRate", 0))
            if payload_rate > 0:
                rec["rate_per_hour"] = round(payload_rate, 2)
                rec["total_deduction"] = round(rec["hours"] * payload_rate, 2)
            else:
                emp_no = str(rec.get("employeeId", "")).strip()
                emp = employee_by_id.get(emp_no)
                if emp:
                    if emp.id not in config_cache:
                        config_cache[emp.id] = await get_synced_employee_payroll_config(emp.id, emp.employeeId, f"{emp.lastName}, {emp.firstName}")
                    config = config_cache[emp.id]
                    if config:
                        hourly_rate = (float(config.basicSalary) / 26.0) / 8.0
                        rec["rate_per_hour"] = round(hourly_rate, 2)
                        rec["total_deduction"] = round(rec["hours"] * hourly_rate, 2)
        except Exception as e:
            print(f"Error calculating undertime for {rec.get('employeeId')}: {e}")
        enriched.append(rec)
    return enriched
