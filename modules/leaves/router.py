from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import require_admin, require_user
from integrations.hr.adapter import get_synced_employee_by_id, get_synced_leave_list


router = APIRouter(
    prefix="/leaves",
    tags=["Leave Management"],
    dependencies=[Depends(require_user)],
)


@router.get("/internal-logs")
async def get_internal_leave_logs(_: object = Depends(require_admin)):
    """Returns synced leave records for internal payroll review."""
    return await get_synced_leave_list()


@router.get("/logs")
async def get_leave_logs(
    employee_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _: object = Depends(require_admin),
):
    """
    Fetches leave records from the synced HR mirror in our payroll database.
    """
    try:
        now = datetime.now()

        if start_date and end_date:
            if end_date.hour == 0 and end_date.minute == 0:
                end_date = end_date.replace(hour=23, minute=59, second=59)
        elif month:
            start_date = datetime(now.year, month, 1, 0, 0, 0)
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
            start_date = now - timedelta(days=7)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "all":
            start_date = None
            end_date = None

        employee_number = None
        if employee_id:
            employee = await get_synced_employee_by_id(employee_id)
            employee_number = employee.employeeId if employee else employee_id

        return await get_synced_leave_list(employee_number, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching synced leave logs: {str(e)}")


@router.get("/stats")
async def get_leave_stats(_: object = Depends(require_admin)):
    """
    Provides statistics for the 'Approve Status' and 'Leave Summary' cards.
    """
    try:
        now = datetime.now(timezone.utc)
        year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        all_leaves = await get_synced_leave_list()
        approved_leaves = [
            leave
            for leave in all_leaves
            if str(leave.get("status", "")).casefold() == "approved"
        ]

        total_leave_days = 0
        paid_leave_days = 0
        unpaid_leave_days = 0

        for doc in approved_leaves:
            start_raw = doc.get("startDate")
            end_raw = doc.get("endDate")
            if not start_raw or not end_raw:
                continue
            start_dt = start_raw if isinstance(start_raw, datetime) else datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            end_dt = end_raw if isinstance(end_raw, datetime) else datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))

            start_day = max(start_dt.date(), year_start.date())
            end_day = end_dt.date()
            if end_day < start_day:
                continue

            days = (end_day - start_day).days + 1
            total_leave_days += days

            is_paid = doc.get("is_paid", True) is not False
            if is_paid:
                paid_leave_days += days
            else:
                unpaid_leave_days += days

        return {
            "requested": len(all_leaves),
            "approved": len([leave for leave in all_leaves if str(leave.get("status", "")).casefold() == "approved"]),
            "pending": len([leave for leave in all_leaves if str(leave.get("status", "")).casefold() == "pending"]),
            "rejected": len([leave for leave in all_leaves if str(leave.get("status", "")).casefold() in {"rejected", "declined"}]),
            "total_leave": total_leave_days,
            "paid_leave": paid_leave_days,
            "unpaid_leave": unpaid_leave_days,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating leave stats: {str(e)}")
