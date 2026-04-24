from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_admin
from core.database import db
from typing import List, Dict

router = APIRouter(
    prefix="/departments",
    tags=["Department Management"],
    dependencies=[Depends(require_admin)],
)

@router.get("/summary")
async def get_department_summary():
    """
    Groups active employees by department to fill the horizontal cards in Figma (Department.png).
    Returns a list of departments with their respective employee counts.
    """
    try:
        collection = db["SyncedHREmployees"]
        
        # Aggregation Pipeline: Match active, group by department name, count them
        pipeline = [
            {"$match": {"payload.isActive": True}},
            {"$group": {
                "_id": "$payload.department", 
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        cursor = collection.aggregate(pipeline)
        
        results = []
        async for doc in cursor:
            # We rename '_id' to 'name' for cleaner frontend consumption
            results.append({
                "name": doc["_id"] if doc["_id"] else "Unassigned",
                "employee_count": doc["count"]
            })
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation failed: {str(e)}")
