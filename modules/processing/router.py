from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from .service import PayrollProcessingService
from db.models import PayrollSnapshot
import io
import csv

router = APIRouter(prefix="/processing", tags=["Payroll Processing"])

class PayrollRunRequest(BaseModel):
    """Schema for standard full payroll run."""
    start_date: datetime
    end_date: datetime

class SelectivePayrollRequest(PayrollRunRequest):
    """Schema for Figma Wizard Step 2: Selected Employees only."""
    employee_ids: List[str]

@router.post("/run")
async def run_payroll(request: PayrollRunRequest):
    try:
        count = await PayrollProcessingService.run_full_payroll(request.start_date, request.end_date)
        return {"status": "success", "processed_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run-selective")
async def run_selective_payroll(request: SelectivePayrollRequest):
    """Endpoint for Figma Payroll Wizard Step 2."""
    try:
        count = await PayrollProcessingService.run_selective_payroll(
            request.start_date, request.end_date, request.employee_ids
        )
        return {"status": "success", "processed_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[PayrollSnapshot])
async def get_payroll_history(department: Optional[str] = Query(None)):
    """Fetches history with optional department filter (Figma Sorter)."""
    return await PayrollProcessingService.get_payroll_history(department)

@router.get("/export/csv")
async def export_payroll_csv():
    """
    Powers the 'DOWNLOAD' button in Figma.
    Generates a CSV of all payroll snapshots.
    """
    history = await PayrollProcessingService.get_payroll_history()
    
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
