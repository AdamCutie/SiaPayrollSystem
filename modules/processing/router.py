from fastapi import APIRouter, HTTPException
from datetime import datetime
from pydantic import BaseModel
from .service import PayrollProcessingService

# 1. Cleaner Prefix: Changed from "/payroll" to "/processing"
# This prevents the redundant URL: /payroll/payroll/run
# Final URL: POST /payroll/processing/run
router = APIRouter(prefix="/processing", tags=["Payroll Processing"])

# 2. Input Schema for the Request
class PayrollRunRequest(BaseModel):
    """
    Schema representing the date range for a payroll run.
    FastAPI will automatically validate that these are valid ISO dates.
    """
    start_date: datetime
    end_date: datetime

# 3. The API Endpoint
@router.post("/run")
async def run_payroll(request: PayrollRunRequest):
    """
    Endpoint to trigger a full payroll run for the given date range.
    This orchestrates reading from HR, calculating math, and saving to Payroll DB.
    """
    try:
        # 4. Trigger the Processing Service (returns an integer)
        count = await PayrollProcessingService.run_full_payroll(
            request.start_date,
            request.end_date
        )

        # 5. Return a professional JSON response
        return {
            "status": "success",
            "message": f"Successfully processed payroll for {count} employees.",
            "data": {
                "processed_count": count,
                "period_start": request.start_date,
                "period_end": request.end_date
            }
        }

    except Exception as e:
        # 6. Error Handling: Return a 500 status code for server-side failures
        print(f"CRITICAL ERROR: Payroll processing failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred during payroll processing: {str(e)}"
        )
