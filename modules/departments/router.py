from fastapi import APIRouter, HTTPException
from core.database import hr_db
from integrations.hr.adapter import EMPLOYEES_COLLECTION
from typing import List, Dict

router = APIRouter(prefix="/departments", tags=["Department Management"])

@router.get("/summary")
async def get_department_summary():
    """
    Groups active employees by department to fill the horizontal cards in Figma (Department.png).
    Returns a list of departments with their respective employee counts.
    """
    try:
        collection = hr_db[EMPLOYEES_COLLECTION]
        
        # Aggregation Pipeline: Match active, group by department name, count them
        pipeline = [
            {"$match": {"isActive": True}},
            {"$group": {
                "_id": "$department", 
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
