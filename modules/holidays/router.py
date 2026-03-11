from fastapi import APIRouter, HTTPException
from core.database import db
from db.models import Holiday
from typing import List
from datetime import datetime

router = APIRouter(prefix="/holidays", tags=["Holiday Management"])

@router.get("/list", response_model=List[Holiday])
async def get_holiday_list():
    """
    Fetches all holidays for the calendar view and table (Figma: Holiday.png).
    """
    try:
        collection = db["Holidays"]
        cursor = collection.find().sort("date", 1)
        holidays = []
        async for doc in cursor:
            holidays.append(Holiday(**doc))
        return holidays
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching holidays: {str(e)}")

@router.get("/upcoming")
async def get_upcoming_holiday():
    """
    Returns the next holiday for the 'Upcoming Holiday' card in Figma.
    """
    try:
        collection = db["Holidays"]
        now = datetime.now()
        holiday = await collection.find_one({"date": {"$gte": now}}, sort=[("date", 1)])
        
        if not holiday:
            return {"message": "No upcoming holidays"}
            
        return Holiday(**holiday)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching upcoming holiday: {str(e)}")
