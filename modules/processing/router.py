from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from core.auth import CurrentUser, get_current_user, require_admin
from modules.activity_logs.service import ActivityLogService
from .email_service import PayslipEmailService
from .service import PayrollProcessingService
from .scheduler import PayrollSchedulerService
from db.models import PayrollSnapshot, PayrollSchedule
from core.database import db
from bson import ObjectId
import io
import csv

router = APIRouter(
    prefix="/processing",
    tags=["Payroll Processing"],
    dependencies=[Depends(require_admin)],
)

class PayrollRunRequest(BaseModel):
    """Schema for standard full payroll run."""
    start_date: datetime
    end_date: datetime

class SelectivePayrollRequest(PayrollRunRequest):
    """Schema for Figma Wizard Step 2: Selected Employees only."""
    employee_ids: List[str]

class StatusUpdateRequest(BaseModel):
    """Schema for updating a snapshot's status and remarks."""
    status: str
    remarks: Optional[str] = None

class ManualAdjustmentRequest(BaseModel):
    """Request to add a retroactive adjustment."""
    employee_id: str
    employee_number: str
    amount: float
    reason: str

class EmployeeReadiness(BaseModel):
    """Status of an employee's data before payroll processing."""
    id: str
    employee_id: str  # human-readable ID
    full_name: str
    firstName: str
    lastName: str
    department: str
    role: str
    contractType: str
    is_ready: bool
    issues: List[str] = []
    missing_config: bool = False
    
    # Salary Data for Table View
    basicSalary: float = 0.0
    housingAllowance: float = 0.0
    transportAllowance: float = 0.0
    mealAllowance: float = 0.0
    otherAllowances: float = 0.0
    sssLoan: float = 0.0
    pagIbigLoan: float = 0.0
    companyLoan: float = 0.0

class PayrollReadinessResponse(BaseModel):
    """Summary of all active employees and their payroll health."""
    ready_count: int
    incomplete_count: int
    employees: List[EmployeeReadiness]

@router.get("/readiness", response_model=PayrollReadinessResponse)
async def get_payroll_readiness():
    """Endpoint for Figma Wizard Step 2: Pre-flight check."""
    return await PayrollProcessingService.get_payroll_readiness()

@router.get("/adjustments/{employee_id}")
async def get_manual_adjustments(employee_id: str):
    """Fetch all manual adjustments for a specific employee (both pending and applied)."""
    collection = db["ManualAdjustments"]
    cursor = collection.find({"employee_id": employee_id}).sort("created_at", -1)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results

@router.post("/adjustments")
async def add_manual_adjustment(request: ManualAdjustmentRequest, user: CurrentUser = Depends(get_current_user)):
    """Add a manual retroactive adjustment for an employee."""
    collection = db["ManualAdjustments"]
    adjustment = {
        "employee_id": request.employee_id,
        "employee_number": request.employee_number,
        "amount": request.amount,
        "reason": request.reason,
        "is_applied": False,
        "created_at": datetime.now(timezone.utc)
    }
    await collection.insert_one(adjustment)
    
    await ActivityLogService.log_local_activity(
        module="Payroll",
        action="Added manual adjustment",
        target_info=f"Emp: {request.employee_number} | Amount: {request.amount}",
        user=user,
        metadata={"amount": request.amount, "reason": request.reason}
    )
    return {"status": "success"}

@router.delete("/adjustments/{adjustment_id}")
async def delete_manual_adjustment(adjustment_id: str, user: CurrentUser = Depends(get_current_user)):
    """Delete a manual adjustment (only if it hasn't been applied yet)."""
    collection = db["ManualAdjustments"]
    result = await collection.delete_one({"_id": ObjectId(adjustment_id), "is_applied": False})
    if result.deleted_count == 0:
        raise HTTPException(status_code=400, detail="Adjustment not found or already applied to a payslip.")
    
    await ActivityLogService.log_local_activity(
        module="Payroll",
        action="Deleted pending adjustment",
        target_info=f"Adj ID: {adjustment_id}",
        user=user
    )
    return {"status": "success"}

@router.post("/run")
async def run_payroll(request: PayrollRunRequest, user: CurrentUser = Depends(get_current_user)):
    try:
        # 🚀 NEW: Link to Schedule for Arrears/Capital Policy
        collection = db["PayrollSchedules"]
        # Match schedule by exact start/end dates
        schedule = await collection.find_one({
            "period_start": request.start_date,
            "period_end": request.end_date
        })
        
        pay_date = schedule.get("pay_date") if schedule else None
        
        count = await PayrollProcessingService.run_full_payroll(
            request.start_date, request.end_date, pay_date=pay_date
        )

        # Update schedule if found
        if schedule:
            await collection.update_one(
                {"_id": schedule["_id"]},
                {"$set": {
                    "is_processed": True,
                    "processed_at": datetime.now(timezone.utc),
                    "snapshot_count": count
                }}
            )

        await ActivityLogService.log_local_activity(
            module="Payroll",
            action="Ran payroll for all active employees",
            target_info=f"{request.start_date.date()} to {request.end_date.date()} | Processed {count} employees",
            user=user,
            metadata={
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "processed_count": count,
                "mode": "full",
                "pay_date": pay_date.isoformat() if pay_date else None,
                "cycle_name": schedule.get("cycle_name") if schedule else "Manual Run"
            },
        )
        return {"status": "success", "processed_count": count, "pay_date": pay_date}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run-selective")
async def run_selective_payroll(request: SelectivePayrollRequest, user: CurrentUser = Depends(get_current_user)):
    """Endpoint for Figma Payroll Wizard Step 2."""
    try:
        # 🚀 NEW: Link to Schedule for Arrears/Capital Policy
        collection = db["PayrollSchedules"]
        schedule = await collection.find_one({
            "period_start": request.start_date,
            "period_end": request.end_date
        })
        
        pay_date = schedule.get("pay_date") if schedule else None

        count = await PayrollProcessingService.run_selective_payroll(
            request.start_date, request.end_date, request.employee_ids, pay_date=pay_date
        )

        # Update schedule if found
        if schedule:
            await collection.update_one(
                {"_id": schedule["_id"]},
                {"$set": {
                    "is_processed": True,
                    "processed_at": datetime.now(timezone.utc),
                    "snapshot_count": count
                }}
            )

        await ActivityLogService.log_local_activity(
            module="Payroll",
            action="Ran payroll for selected employees",
            target_info=f"{request.start_date.date()} to {request.end_date.date()} | Processed {count} of {len(request.employee_ids)} selected employees",
            user=user,
            metadata={
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "processed_count": count,
                "selected_count": len(request.employee_ids),
                "employee_ids": request.employee_ids,
                "mode": "selective",
                "pay_date": pay_date.isoformat() if pay_date else None,
                "cycle_name": schedule.get("cycle_name") if schedule else "Manual Run"
            },
        )
        return {"status": "success", "processed_count": count, "pay_date": pay_date}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[PayrollSnapshot])
async def get_payroll_history(
    department: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """Fetches history with optional department, period, month, and status filters."""
    return await PayrollProcessingService.get_payroll_history(
        department=department,
        period=period,
        month=month,
        status=status,
        start_date=start_date,
        end_date=end_date
    )

@router.post("/{snapshot_id}/email-send")
async def send_single_payslip_email(snapshot_id: str, user: CurrentUser = Depends(get_current_user)):
    try:
        result = await PayslipEmailService.send_snapshot_email(snapshot_id, force_retry=True)
        await ActivityLogService.log_local_activity(
            module="Payroll",
            action="Manually triggered payslip email",
            target_info=f"Snapshot ID: {snapshot_id}",
            user=user,
            metadata=result,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send payslip email: {exc}")


@router.post("/email-send-due")
async def send_due_payslip_emails(user: CurrentUser = Depends(get_current_user)):
    try:
        result = await PayslipEmailService.process_due_payslip_emails()
        await ActivityLogService.log_local_activity(
            module="Payroll",
            action="Triggered due payslip emails",
            target_info=f"Processed {result.get('processed', 0)} due email(s)",
            user=user,
            metadata=result,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send due payslip emails: {exc}")


@router.post("/email-resend-failed")
async def resend_failed_payslip_emails(user: CurrentUser = Depends(get_current_user)):
    try:
        result = await PayslipEmailService.resend_failed_or_skipped()
        await ActivityLogService.log_local_activity(
            module="Payroll",
            action="Triggered bulk payslip email resend",
            target_info=f"Processed {result.get('processed', 0)} retry email(s)",
            user=user,
            metadata=result,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resend payslip emails: {exc}")

@router.get("/schedule", response_model=List[PayrollSchedule])
async def get_payroll_schedule(year: int = 2026):
    """Fetches the 24 cycles for the given year."""
    collection = db["PayrollSchedules"]
    cursor = collection.find({"year": year}).sort("period_start", 1)
    return [PayrollSchedule(**doc) async for doc in cursor]

@router.patch("/schedule/automation")
async def toggle_automation(enabled: bool, user: CurrentUser = Depends(get_current_user)):
    """Toggles automation ON/OFF for all future cycles."""
    collection = db["PayrollSchedules"]
    await collection.update_many(
        {"is_processed": False},
        {"$set": {"automation_on": enabled}}
    )
    
    await ActivityLogService.log_local_activity(
        module="Payroll",
        action=f"Automation toggled {'ON' if enabled else 'OFF'}",
        user=user
    )
    return {"status": "success", "automation_on": enabled}

@router.patch("/history/{snapshot_id}/status")
async def update_snapshot_status(
    snapshot_id: str, 
    request: StatusUpdateRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Update the status of a specific payroll record.
    Used for Finance approvals/rejections.
    """
    success = await PayrollProcessingService.update_snapshot_status(
        snapshot_id, request.status, request.remarks
    )
    if not success:
        raise HTTPException(status_code=404, detail="Payroll record not found or no changes made.")
    
    await ActivityLogService.log_local_activity(
        module="Payroll",
        action=f"Updated status to {request.status}",
        target_info=f"Snapshot ID: {snapshot_id}",
        user=user,
        metadata={"status": request.status, "remarks": request.remarks}
    )
    return {"status": "success"}

@router.get("/export/csv")
async def export_payroll_csv(user: CurrentUser = Depends(get_current_user)):
    """
    Powers the 'DOWNLOAD' button in Figma.
    Generates a CSV of all payroll snapshots.
    """
    history = await PayrollProcessingService.get_payroll_history()
    await ActivityLogService.log_local_activity(
        module="Payroll",
        action="Exported payroll history CSV",
        target_info=f"Exported {len(history)} payroll snapshot rows",
        user=user,
        metadata={"rows": len(history), "format": "csv"},
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee", "Basic", "Gross", "Deductions", "Net", "Processed At"])
    
    for record in history:
        writer.writerow([
            record.full_name, record.basic_salary, record.gross_pay, 
            record.total_deductions, record.net_pay, record.processed_at
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payroll_export.csv"}
    )
