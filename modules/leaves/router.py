from fastapi import APIRouter, Depends, HTTPException

from core.auth import CurrentUser, get_current_user, require_admin, require_user
from core.database import db
from db.models import LeaveRequest
from typing import List
from datetime import datetime, timezone
from pydantic import BaseModel

router = APIRouter(
    prefix="/leaves",
    tags=["Leave Management"],
    dependencies=[Depends(require_user)],
)

class LeaveApplyRequest(BaseModel):
    """Schema for employee-side leave application."""
    employee_id: str
    full_name: str
    employee_number: str
    leave_type: str
    start_date: datetime
    end_date: datetime
    is_paid: bool = True

@router.post("/apply")
async def apply_for_leave(request: LeaveApplyRequest, user: CurrentUser = Depends(get_current_user)):
    """
    Allows an employee to submit a leave request (Figma: Employee flow).
    Defaults to 'Pending' status.
    """
    if user.role != "admin" and request.employee_id != user.employee_id:
        raise HTTPException(status_code=403, detail="Employees can only apply leave for themselves.")
    try:
        collection = db["LeaveRequests"]
        new_leave = request.model_dump()
        new_leave["status"] = "Pending"
        await collection.insert_one(new_leave)
        return {"message": "Leave request submitted successfully and is awaiting admin approval."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit leave: {str(e)}")

@router.get("/logs", response_model=List[LeaveRequest])
async def get_leave_logs(_: object = Depends(require_admin)):
    """
    Fetches all leave requests for the Admin table (Figma: Leave.png).
    """
    try:
        collection = db["LeaveRequests"]
        cursor = collection.find().sort("start_date", -1)
        logs = []
        async for doc in cursor:
            logs.append(LeaveRequest(**doc))
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching leave logs: {str(e)}")

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
