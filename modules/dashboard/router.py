from fastapi import APIRouter, Depends

from core.auth import require_admin
from core.database import db, hr_db
from integrations.hr.adapter import EMPLOYEES_COLLECTION
from .schemas import DashboardOverview

# --- Dashboard metric definitions (easy to change) ---
# Which payroll-db collections count as "approval work items" for the admin dashboard?
APPROVAL_SOURCES: list[str] = [
    "AttendanceLogs",
    "LeaveRequests",
    "OvertimeRecords",
    "PenaltyRecords",
]

APPROVAL_STATUSES: tuple[str, ...] = ("Approved", "Pending", "Rejected")
TOP_DEPARTMENTS_LIMIT = 5


async def _status_counts(collection_name: str) -> dict[str, int]:
    """
    Returns {status: count} for a collection, defaulting missing status -> "Pending".
    """
    coll = db[collection_name]
    pipeline = [
        {"$project": {"status": {"$ifNull": ["$status", "Pending"]}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    rows = await coll.aggregate(pipeline).to_list(None)
    return {str(r["_id"]): int(r["count"]) for r in rows if r.get("_id") is not None}


# Initialize the Router
router = APIRouter(
    prefix="/overview",
    tags=["Admin Dashboard"],
    dependencies=[Depends(require_admin)],
)

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

    # 1b. Department breakdown (top N)
    dept_pipeline = [
        {"$match": {"isActive": True}},
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": TOP_DEPARTMENTS_LIMIT},
    ]
    dept_rows = await hr_coll.aggregate(dept_pipeline).to_list(None)
    departments = {
        (row.get("_id") or "Unassigned"): int(row.get("count", 0))
        for row in dept_rows
    }
    
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

    delayed_pipeline = [
        {"$match": {"status": {"$ne": "Completed"}}},
        {"$group": {"_id": None, "total": {"$sum": "$net_pay"}}},
    ]
    delayed_data = await payroll_coll.aggregate(delayed_pipeline).to_list(1)
    delayed_payout = delayed_data[0]["total"] if delayed_data else 0.0

    # 3. "Approvals" work queue (real data)
    approvals_requested = 0
    approvals_approved = 0
    approvals_pending = 0
    approvals_rejected = 0

    for source in APPROVAL_SOURCES:
        counts = await _status_counts(source)
        approvals_requested += sum(counts.values())
        approvals_approved += counts.get("Approved", 0)
        approvals_pending += counts.get("Pending", 0)
        approvals_rejected += counts.get("Rejected", 0)

    # 4. Return Combined Stats
    return {
        "employees": {
            "total": total,
            "regular": regular,
            "probationary": total - regular
        },
        "approvals": {
            "requested": approvals_requested,
            "approved": approvals_approved,
            "pending": approvals_pending,
            "rejected": approvals_rejected,
        },
        "payouts": {
            "total_payout": round(total_payout, 2),
            "delayed_payout": round(delayed_payout, 2),
            "average_salary": round(avg_salary, 2)
        },
        "departments": departments,
    }
