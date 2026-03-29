from fastapi import APIRouter, Depends, HTTPException

from core.auth import CurrentUser, get_current_user, require_admin, require_user
from integrations.hr.adapter import get_hr_leaves_list
from typing import List, Optional
from datetime import datetime, timezone

router = APIRouter(
    prefix="/leaves",
    tags=["Leave Management"],
    dependencies=[Depends(require_user)],
)

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta, timezone

from db.models import LeaveRequest
from core.database import db

@router.get("/internal-logs", response_model=List[LeaveRequest])
async def get_internal_leave_logs(_: object = Depends(require_admin)):
    """Fetches leave records from OUR Payroll Database (matches Dashboard count)."""
    collection = db["LeaveRequests"]
    cursor = collection.find().sort("start_date", -1)
    return [LeaveRequest(**doc) async for doc in cursor]

@router.get("/logs")
async def get_leave_logs(
    employee_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None), # today, yesterday, lastweek
    month: Optional[int] = Query(None), # 1-12
    _: object = Depends(require_admin)
):
    """
    Fetches real-time leave records from the Legacy HR System (Source of Truth).
    Returns raw data for UI viewing.
    """
    try:
        start_date = None
        end_date = None
        
        now = datetime.now()
        
        if month:
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

        return await get_hr_leaves_list(employee_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching HR leave logs: {str(e)}")

@router.get("/stats")
async def get_leave_stats(_: object = Depends(require_admin)):
    """
    Provides statistics for the 'Approve Status' and 'Leave Summary' cards.
    """
    try:
        coll = db["LeaveRequests"]
        now = datetime.now(timezone.utc)
        year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)

        # Annual leave usage summary (easy to change later):
        # - "total_leave"  = total APPROVED leave days YTD
        # - "paid_leave"   = total APPROVED paid leave days YTD
        # - "unpaid_leave" = total APPROVED unpaid leave days YTD
        approved_leaves = await coll.find(
            {"status": "Approved", "end_date": {"$gte": year_start}}
        ).to_list(None)

        total_leave_days = 0
        paid_leave_days = 0
        unpaid_leave_days = 0

        for doc in approved_leaves:
            start_dt: datetime = doc.get("start_date")
            end_dt: datetime = doc.get("end_date")
            if not start_dt or not end_dt:
                continue

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
            "requested": await coll.count_documents({}),
            "approved": await coll.count_documents({"status": "Approved"}),
            "pending": await coll.count_documents({"status": "Pending"}),
            "rejected": await coll.count_documents({"status": "Rejected"}),
            "total_leave": total_leave_days,
            "paid_leave": paid_leave_days,
            "unpaid_leave": unpaid_leave_days,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating leave stats: {str(e)}")
