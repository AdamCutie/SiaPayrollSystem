from fastapi import APIRouter, HTTPException
from core.database import db
from db.models import LeaveRequest
from typing import List
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/leaves", tags=["Leave Management"])

class LeaveApplyRequest(BaseModel):
    """Schema for employee-side leave application."""
    employee_id: str
    full_name: str
    employee_number: str
    leave_type: str
    start_date: datetime
    end_date: datetime

@router.post("/apply")
async def apply_for_leave(request: LeaveApplyRequest):
    """
    Allows an employee to submit a leave request (Figma: Employee flow).
    Defaults to 'Pending' status.
    """
    try:
        collection = db["LeaveRequests"]
        new_leave = request.model_dump()
        new_leave["status"] = "Pending"
        await collection.insert_one(new_leave)
        return {"message": "Leave request submitted successfully and is awaiting admin approval."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit leave: {str(e)}")

@router.get("/logs", response_model=List[LeaveRequest])
async def get_leave_logs():
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
async def get_leave_stats():
    """
    Provides statistics for the 'Approve Status' and 'Leave Summary' cards.
    """
    try:
        coll = db["LeaveRequests"]
        return {
            "requested": await coll.count_documents({}),
            "approved": await coll.count_documents({"status": "Approved"}),
            "pending": await coll.count_documents({"status": "Pending"}),
            "rejected": await coll.count_documents({"status": "Rejected"}),
            "total_leave": 15, # Placeholder to match Figma design
            "paid_leave": 78,
            "unpaid_leave": 6
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating leave stats: {str(e)}")
