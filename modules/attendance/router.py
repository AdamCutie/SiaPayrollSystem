from fastapi import APIRouter, HTTPException, Query
from core.database import db
from db.models import AttendanceLog, PenaltyRecord, OvertimeRecord
from typing import List, Optional
from bson import ObjectId

router = APIRouter(prefix="/attendance", tags=["Attendance & Work Log"])

@router.get("/logs", response_model=List[AttendanceLog])
async def get_all_work_logs(
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    position: Optional[str] = Query(None)
):
    """
    Fetches work logs with filtering (Figma: Sort By, Department, Position dropdowns).
    """
    try:
        collection = db["AttendanceLogs"]
        query = {}
        if department: query["department"] = department
        if status: query["status"] = status
        if position: query["position"] = position
        
        cursor = collection.find(query).sort("date", -1)
        logs = []
        async for doc in cursor:
            logs.append(AttendanceLog(**doc))
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch work logs: {str(e)}")

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

@router.patch("/status/{log_id}")
async def update_log_status(log_id: str, status: str):
    """
    Updates the approval status of a work log (Matches the 'Action' column in Figma).
    Supported statuses: 'Approved', 'Rejected', 'Pending'
    """
    if status not in ["Approved", "Rejected", "Pending"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be Approved, Rejected, or Pending.")
        
    try:
        collection = db["AttendanceLogs"]
        result = await collection.update_one(
            {"_id": ObjectId(log_id)},
            {"$set": {"status": status}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Attendance log record not found.")
            
        return {"message": f"Successfully updated log status to {status}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error during update: {str(e)}")
