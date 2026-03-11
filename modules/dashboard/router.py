from fastapi import APIRouter
from core.database import db, hr_db
from integrations.hr.adapter import EMPLOYEES_COLLECTION
from .schemas import DashboardOverview

# Initialize the Router
router = APIRouter(prefix="/overview", tags=["Admin Dashboard"])

@router.get("/", response_model=DashboardOverview)
async def get_dashboard_overview():
    """
    The 'Brain' for the Admin Overview Page.
    Fetches real-time employee counts from HR and financial totals from Payroll.
    """
    # 1. Fetch Employee Identity Stats from Legacy HR (Read-Only)
    hr_coll = hr_db[EMPLOYEES_COLLECTION]
    total = await hr_coll.count_documents({"isActive": True})
    regular = await hr_coll.count_documents({"isActive": True, "contractType": "Regular"})
    
    # 2. Fetch Financial Totals from Our New Payroll Snapshots
    payroll_coll = db["PayrollSnapshots"]
    # MongoDB Aggregation to sum up all net_pays from past runs
    pipeline = [
        {"$group": {
            "_id": None, 
            "total": {"$sum": "$net_pay"}, 
            "avg": {"$avg": "$basic_salary"}
        }}
    ]
    payout_data = await payroll_coll.aggregate(pipeline).to_list(1)
    
    total_payout = payout_data[0]["total"] if payout_data else 0.0
    avg_salary = payout_data[0]["avg"] if payout_data else 0.0

    # 3. Return Combined Stats (Mocking approval counts for UI display)
    return {
        "employees": {
            "total": total,
            "regular": regular,
            "provisional": total - regular
        },
        "approvals": {
            "requested": 282, 
            "approved": 78, 
            "pending": 6, 
            "rejected": 5
        },
        "payouts": {
            "total_payout": round(total_payout, 2),
            "delayed_payout": 500.0,
            "average_salary": round(avg_salary, 2)
        },
        "departments": {
            "IT": 6, 
            "HR": 4, 
            "Sales": 2, 
            "Finance": 5, 
            "Operations": 3
        }
    }
