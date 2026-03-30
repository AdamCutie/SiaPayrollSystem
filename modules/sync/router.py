from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import require_admin
from .service import HRSyncService, SYNC_TARGETS


router = APIRouter(
    prefix="/sync/hr",
    tags=["HR Sync"],
    dependencies=[Depends(require_admin)],
)


class HRSyncConfigUpdate(BaseModel):
    auto_sync_enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1)


@router.get("/status")
async def get_hr_sync_status():
    return await HRSyncService.get_status()


@router.get("/config")
async def get_hr_sync_config():
    return await HRSyncService.get_runtime_config()


@router.post("/config")
async def update_hr_sync_config(payload: HRSyncConfigUpdate):
    try:
        return await HRSyncService.update_runtime_config(
            auto_sync_enabled=payload.auto_sync_enabled,
            interval_minutes=payload.interval_minutes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update HR sync config: {exc}")


@router.post("/run")
async def run_hr_sync(
    targets: list[str] | None = Query(None, description="Subset of sync targets"),
):
    try:
        selected = targets or list(SYNC_TARGETS.keys())
        return await HRSyncService.run_sync(selected, mode="manual")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HR sync failed: {exc}")
