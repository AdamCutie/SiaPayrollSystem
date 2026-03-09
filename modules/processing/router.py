from fastapi import APIRouter, HTTPException
from datetime import datetime
from pydantic import BaseModel
from .service import PayrollProcessingService

# Initialize the Router
router = APIRouter(prefix="/payroll", tags=["PayrollProcessing"])

# Schema for the incoming Request


class PayrollRunRequest(BaseModel):
    start_date: datetime
    end_date: datetime

# The API Endpoint


@router.post("/run")
async def run_payroll(request: PayrollRunRequest):
    """
    Endpoint to trigger a full payroll run for the given
    date range.
    """
    try:
        # Trigger the orchestrator service
        count = await PayrollProcessingService.run_full_payroll(
            request.start_date,
            request.end_date
        )

    # Return a success message
        return {
            "status": "success",
            "message": f"Successfully processed payroll for {count} employees.",
            "processed_count": count
        }

    except Exception as e:
        # if anything goes wrong, return a 500 server error
        raise HTTPException(status_code=500, detail=str(e))
