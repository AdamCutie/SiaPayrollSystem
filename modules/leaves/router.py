from fastapi import APIRouter, HTTPException
from core.database import db
from db.models import LeaveRequest
from typing import List

router = APIRouter(prefix="/leaves", tags=["Leave Management"])

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
