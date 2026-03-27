from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import require_admin
from core.database import db
from integrations.hr.adapter import get_hr_attendance_list
from db.models import PenaltyRecord, OvertimeRecord
from typing import List, Optional
from bson import ObjectId

router = APIRouter(
    prefix="/attendance",
    tags=["Attendance & Work Log"],
    dependencies=[Depends(require_admin)],
)

from datetime import datetime, timedelta

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
