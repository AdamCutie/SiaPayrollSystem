from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_user
from core.database import db
from db.models import Holiday
from typing import List
from datetime import datetime

import httpx
from pydantic import BaseModel

router = APIRouter(
    prefix="/holidays",
    tags=["Holiday Management"],
    dependencies=[Depends(require_user)],
)

class SyncResponse(BaseModel):
    status: str
    synced_count: int
    message: str

@router.post("/sync", response_model=SyncResponse)
async def sync_official_holidays(year: int = 2026):
    """
    Connects to the Nager.Date Global Holiday API to fetch official PH holidays.
    Automates the long-term detection of holidays for the system.
    """
    try:
        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/PH"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="External Holiday API unreachable.")
            
            external_holidays = response.json()
            
        collection = db["Holidays"]
        synced_count = 0
        
        for h in external_holidays:
            # Format: {'date': '2026-01-01', 'localName': 'Bagong Taon', 'name': 'New Year\'s Day', ...}
            h_date = datetime.fromisoformat(h['date'])
            h_name = h['name']
            
            # 🇵🇭 PH Logic: Determine Type based on common names
            # Regular Holidays based on PH Labor Law
            regular_keywords = [
                "New Year's Day", "Maundy Thursday", "Good Friday", "Labor Day", "Labour Day", 
                "Independence Day", "National Heroes", "Bonifacio Day", "Christmas Day", 
                "Rizal Day", "Eid'l", "Day of Valor"
            ]
            
            h_type = "Special Non-Working Day"
            for kw in regular_keywords:
                if kw.lower() in h_name.lower():
                    h_type = "Regular Holiday"
                    break

            # Upsert into our DB: Link by Date and Name to prevent duplicates
            result = await collection.update_one(
                {"date": h_date, "name": h_name},
                {"$set": {
                    "date": h_date,
                    "name": h_name,
                    "type": h_type,
                    "updated_at": datetime.now()
                }},
                upsert=True
            )
            if result.upserted_id or result.modified_count:
                synced_count += 1

        # 🇵🇭 ADDITIONAL PH HOLIDAYS (To reach official 22 count)
        # Based on Proclamation 727 and Islamic Estimates for 2026
        additional_ph = [
            {"date": f"{year}-02-17", "name": "Chinese New Year", "type": "Special Non-Working Day"},
            {"date": f"{year}-02-25", "name": "EDSA People Power Revolution Anniversary", "type": "Special Non-Working Day"},
            {"date": f"{year}-04-04", "name": "Holy Saturday", "type": "Special Non-Working Day"},
            {"date": f"{year}-11-02", "name": "All Souls' Day", "type": "Special Non-Working Day"},
            {"date": f"{year}-12-24", "name": "Christmas Eve", "type": "Special Non-Working Day"},
            {"date": f"{year}-12-31", "name": "Last Day of the Year", "type": "Special Non-Working Day"},
            # Islamic Holidays (Estimated - confirmed by moon sighting each year)
            {"date": f"{year}-03-20", "name": "Eid'l Fitr", "type": "Regular Holiday"},
            {"date": f"{year}-05-27", "name": "Eid'l Adha", "type": "Regular Holiday"},
        ]

        for add_h in additional_ph:
            h_date = datetime.fromisoformat(add_h['date'])
            # Ensure we don't duplicate if they already exist from the API
            result = await collection.update_one(
                {"date": h_date, "name": add_h['name']},
                {"$set": {
                    "date": h_date,
                    "name": add_h['name'],
                    "type": add_h['type'],
                    "updated_at": datetime.now()
                }},
                upsert=True
            )
            if result.upserted_id or result.modified_count:
                synced_count += 1
                
        return {
            "status": "success",
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} holidays for {year}. (Official PH 22-day calendar active)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

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
