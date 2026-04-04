from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import CurrentUser, get_current_user, require_user
from .service import ActivityLogService


router = APIRouter(
    prefix="/activity-logs",
    tags=["Activity Logs"],
    dependencies=[Depends(require_user)],
)


class ActivityLogTrackRequest(BaseModel):
    module: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=200)
    target_info: str = Field(default="", max_length=500)
    visibility: str = Field(default="HR & Payroll", max_length=100)
    metadata: dict = Field(default_factory=dict)


@router.get("")
async def get_activity_logs(
    limit: int = Query(100, ge=1, le=500),
    source: str = Query("all", pattern="^(all|hr|payroll)$"),
    period: str = Query("today", pattern="^(today|yesterday|week|month|all)$"),
):
    try:
        return await ActivityLogService.get_combined_activity_logs(limit=limit, source=source, period=period)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch activity logs: {exc}")


@router.post("/track")
async def track_activity_log(payload: ActivityLogTrackRequest, user: CurrentUser = Depends(get_current_user)):
    try:
        return await ActivityLogService.log_local_activity(
            module=payload.module,
            action=payload.action,
            target_info=payload.target_info,
            user=user,
            visibility=payload.visibility,
            metadata=payload.metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to record activity log: {exc}")
