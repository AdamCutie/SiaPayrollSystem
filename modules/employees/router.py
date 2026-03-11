from fastapi import APIRouter, HTTPException
from core.database import db, hr_db
from integrations.hr.adapter import EMPLOYEES_COLLECTION, get_employee_payroll_config
from db.models import PayrollSnapshot
from typing import List

router = APIRouter(prefix="/employees", tags=["Employee Management"])

@router.get("/list")
async def get_employee_list():
    """
    Fetches the list of all active employees for the management table.
    """
    try:
        hr_coll = hr_db[EMPLOYEES_COLLECTION]
        # Fetching top 100 active employees from HR system
        employees = await hr_coll.find({"isActive": True}).to_list(100)
        return employees
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch employees: {str(e)}")

@router.get("/profile/{employee_id}")
async def get_employee_profile(employee_id: str):
    """
    Full Profile View: Combines HR Identity with Payroll History Snapshots.
    """
    try:
        # 1. Identity from HR (Adapter handles the multi-link search)
        hr_info = await get_employee_payroll_config(employee_id, "", "")
        
        if not hr_info:
            raise HTTPException(status_code=404, detail="Employee profile not found.")

        # 2. History from our New Database
        history_coll = db["PayrollSnapshots"]
        history = await history_coll.find({"employee_id": employee_id}).sort("processed_at", -1).to_list(10)
        
        return {
            "identity": hr_info,
            "payroll_history": history,
            "status": "Active" if hr_info.isActive else "Inactive"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")
