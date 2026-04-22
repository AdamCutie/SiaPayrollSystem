from fastapi import APIRouter, Depends

from core.auth import require_admin
from core.database import db
from .schemas import DashboardOverview
TOP_DEPARTMENTS_LIMIT = 5


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
    # 1. Fetch Employee Identity Stats from synced HR mirror
    hr_coll = db["SyncedHREmployees"]
    total = await hr_coll.count_documents({"payload.isActive": True})
    regular = await hr_coll.count_documents({"payload.isActive": True, "payload.contractType": "Regular"})

    # 1b. Department breakdown (top N)
    dept_pipeline = [
        {"$match": {"payload.isActive": True}},
        {"$group": {"_id": "$payload.department", "count": {"$sum": 1}}},
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
    # MongoDB Aggregation to sum up all net_pays from past APPROVED or COMPLETED runs
    pipeline = [
        {"$match": {"status": {"$regex": "^\s*(Approved|Completed)\s*$", "$options": "i"}}},
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
        {"$match": {"status": {"$regex": "^\s*(Pending|Delayed)\s*$", "$options": "i"}}},
        {"$group": {"_id": None, "total": {"$sum": "$net_pay"}}},
    ]
    delayed_data = await payroll_coll.aggregate(delayed_pipeline).to_list(1)
    delayed_payout = delayed_data[0]["total"] if delayed_data else 0.0

    rejected_pipeline = [
        {"$match": {"status": {"$regex": "^\s*(Rejected|Declined)\s*$", "$options": "i"}}},
        {"$group": {"_id": None, "total": {"$sum": "$net_pay"}}},
    ]
    rejected_data = await payroll_coll.aggregate(rejected_pipeline).to_list(1)
    rejected_payout = rejected_data[0]["total"] if rejected_data else 0.0

    # 3. "Approvals" work queue (real data)
    approvals_requested = 0
    approvals_approved = 0
    approvals_pending = 0
    approvals_rejected = 0

    # 3c. Payroll Snapshots (New: Pending/Approved/Rejected)
    p_total = await payroll_coll.count_documents({})
    p_app = await payroll_coll.count_documents({"status": {"$regex": "^(Approved|Completed)$", "$options": "i"}})
    p_pen = await payroll_coll.count_documents({"status": {"$regex": "^(Pending|Delayed)$", "$options": "i"}})
    p_rej = await payroll_coll.count_documents({"status": {"$regex": "^(Rejected|Declined)$", "$options": "i"}})

    approvals_requested += p_total
    approvals_approved += p_app
    approvals_pending += p_pen
    approvals_rejected += p_rej

    # 3d. Undertime Records
    ut_coll = db["SyncedHRUndertimeRecords"]
    ut_total = await ut_coll.count_documents({})
    # Assuming synced means detected for now
    approvals_requested += ut_total
    approvals_pending += ut_total

    # 3a. Leaves from synced HR mirror
    hr_leave_coll = db["SyncedHRLeaves"]
    l_total = await hr_leave_coll.count_documents({})
    l_app = await hr_leave_coll.count_documents({"status": {"$regex": "^approved$", "$options": "i"}})
    l_pen = await hr_leave_coll.count_documents({"status": {"$regex": "^pending$", "$options": "i"}})
    l_rej = await hr_leave_coll.count_documents({"status": {"$regex": "^(rejected|declined)$", "$options": "i"}})

    approvals_requested += l_total
    approvals_approved += l_app
    approvals_pending += l_pen
    approvals_rejected += l_rej

    # 3b. Overtime statuses from synced HR mirror
    hr_ot_coll = db["SyncedHROvertimeRequests"]
    o_total = await hr_ot_coll.count_documents({})
    o_app = await hr_ot_coll.count_documents({"status": {"$regex": "^approved$", "$options": "i"}})
    o_pen = await hr_ot_coll.count_documents({"status": {"$regex": "^pending$", "$options": "i"}})
    o_rej = await hr_ot_coll.count_documents({"status": {"$regex": "^(rejected|declined)$", "$options": "i"}})

    approvals_requested += o_total
    approvals_approved += o_app
    approvals_pending += o_pen
    approvals_rejected += o_rej

    # 3e. Fetch Recent Rejected/Declined Payroll for Dashboard Alerts
    rejected_cursor = payroll_coll.find({"status": {"$regex": "^(Rejected|Declined)$", "$options": "i"}}).sort("processed_at", -1).limit(5)
    recent_rejections = []
    async for doc in rejected_cursor:
        recent_rejections.append({
            "id": str(doc["_id"]),
            "employee_number": doc["employee_number"],
            "full_name": doc["full_name"],
            "net_pay": doc["net_pay"],
            "remarks": doc.get("remarks"),
            "processed_at": doc["processed_at"]
        })

    # 🚀 REMOVED: Attendance Logs (HR) are no longer counted in Approval Status

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
            "rejected_payout": round(rejected_payout, 2),
            "average_salary": round(avg_salary, 2)
        },
        "departments": departments,
        "recent_rejections": recent_rejections
    }
