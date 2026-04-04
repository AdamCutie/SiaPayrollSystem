from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from bson import Decimal128, ObjectId

from core.config import settings
from core.database import db, hr_db
from modules.activity_logs.service import ActivityLogService


SYNC_TARGETS = {
    "employees": ("Employees", "SyncedHREmployees"),
    "payroll_configurations": ("PayrollConfigurations", "SyncedHRPayrollConfigurations"),
    "attendance": ("Attendance", "SyncedHRAttendance"),
    "leaves": ("Leaves", "SyncedHRLeaves"),
    "overtime_requests": ("OvertimeRequests", "SyncedHROvertimeRequests"),
}


class HRSyncService:
    _task: asyncio.Task | None = None
    _stop_event: asyncio.Event | None = None
    CONFIG_SCOPE = "hr-sync-config"
    STATUS_SCOPE = "hr-sync"

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    async def _get_config_doc(cls) -> dict | None:
        return await db["HRSyncState"].find_one({"scope": cls.CONFIG_SCOPE})

    @classmethod
    async def get_runtime_config(cls) -> dict:
        config_doc = await cls._get_config_doc()
        auto_sync_enabled = settings.AUTO_SYNC_HR
        interval_minutes = settings.AUTO_SYNC_INTERVAL_MINUTES

        if config_doc:
            auto_sync_enabled = bool(config_doc.get("auto_sync_enabled", auto_sync_enabled))
            interval_minutes = int(config_doc.get("interval_minutes", interval_minutes))

        return {
            "scope": cls.CONFIG_SCOPE,
            "auto_sync_enabled": auto_sync_enabled,
            "interval_minutes": max(1, interval_minutes),
        }

    @classmethod
    async def update_runtime_config(
        cls,
        *,
        auto_sync_enabled: bool | None = None,
        interval_minutes: int | None = None,
    ) -> dict:
        current = await cls.get_runtime_config()
        updated = {
            "scope": cls.CONFIG_SCOPE,
            "auto_sync_enabled": current["auto_sync_enabled"] if auto_sync_enabled is None else bool(auto_sync_enabled),
            "interval_minutes": current["interval_minutes"] if interval_minutes is None else max(1, int(interval_minutes)),
            "updated_at": cls._utc_now(),
        }
        await db["HRSyncState"].update_one(
            {"scope": cls.CONFIG_SCOPE},
            {"$set": updated},
            upsert=True,
        )

        if updated["auto_sync_enabled"]:
            await cls.start_auto_sync()
        else:
            await cls.stop_auto_sync()

        return await cls.get_runtime_config()

    @classmethod
    def _normalize_value(cls, value: Any):
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, Decimal128):
            return float(value.to_decimal())
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [cls._normalize_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): cls._normalize_value(v) for k, v in value.items()}
        return value

    @classmethod
    def _document_hash(cls, document: dict) -> str:
        normalized = cls._normalize_value(document)
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _build_sync_doc(cls, source_collection: str, document: dict) -> dict:
        payload = cls._normalize_value(document)
        return {
            "source_id": str(document.get("_id")),
            "source_collection": source_collection,
            "source_hash": cls._document_hash(document),
            "source_updated_at": payload.get("updatedAt") or payload.get("updated_at"),
            "employee_number": payload.get("employeeId") or payload.get("employeeNumber"),
            "status": payload.get("status"),
            "date": payload.get("date"),
            "start_date": payload.get("startDate"),
            "end_date": payload.get("endDate"),
            "last_synced_at": cls._utc_now(),
            "payload": payload,
        }

    @classmethod
    async def _sync_target(cls, target_key: str) -> dict:
        if target_key not in SYNC_TARGETS:
            raise ValueError(f"Unsupported sync target: {target_key}")

        source_collection, target_collection = SYNC_TARGETS[target_key]
        source_coll = hr_db[source_collection]
        target_coll = db[target_collection]

        inserted = 0
        updated = 0
        unchanged = 0

        async for doc in source_coll.find({}):
            sync_doc = cls._build_sync_doc(source_collection, doc)
            existing = await target_coll.find_one({"source_id": sync_doc["source_id"]})

            if existing and existing.get("source_hash") == sync_doc["source_hash"]:
                unchanged += 1
                await target_coll.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"last_synced_at": sync_doc["last_synced_at"]}},
                )
                continue

            result = await target_coll.update_one(
                {"source_id": sync_doc["source_id"]},
                {"$set": sync_doc, "$setOnInsert": {"created_at": cls._utc_now()}},
                upsert=True,
            )
            if result.upserted_id:
                inserted += 1
            else:
                updated += 1

        return {
            "target": target_key,
            "source_collection": source_collection,
            "target_collection": target_collection,
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
        }

    @classmethod
    async def run_sync(cls, targets: list[str] | None = None, mode: str = "manual") -> dict:
        sync_targets = targets or list(SYNC_TARGETS.keys())
        started_at = cls._utc_now()
        results = []

        try:
            for target in sync_targets:
                results.append(await cls._sync_target(target))

            status = "success"
            error = None
        except Exception as exc:
            status = "failed"
            error = str(exc)

        summary = {
            "status": status,
            "mode": mode,
            "targets": sync_targets,
            "started_at": started_at,
            "completed_at": cls._utc_now(),
            "results": results,
            "error": error,
        }

        await db["HRSyncState"].update_one(
            {"scope": cls.STATUS_SCOPE},
            {"$set": {**summary, "scope": cls.STATUS_SCOPE}},
            upsert=True,
        )
        if status == "success":
            await ActivityLogService.log_local_activity(
                module="Synchronization",
                action="Completed HR synchronization",
                target_info=", ".join(sync_targets),
                actor_name="System",
                metadata={
                    "mode": mode,
                    "targets": sync_targets,
                    "results": results,
                    "completed_at": summary["completed_at"].isoformat(),
                },
            )
        if error:
            raise RuntimeError(error)
        return summary

    @classmethod
    async def get_status(cls) -> dict:
        doc = await db["HRSyncState"].find_one({"scope": cls.STATUS_SCOPE})
        runtime_config = await cls.get_runtime_config()
        if not doc:
            return {
                "scope": cls.STATUS_SCOPE,
                "status": "never_run",
                "auto_sync_enabled": runtime_config["auto_sync_enabled"],
                "interval_minutes": runtime_config["interval_minutes"],
            }

        doc["_id"] = str(doc["_id"])
        doc["auto_sync_enabled"] = runtime_config["auto_sync_enabled"]
        doc["interval_minutes"] = runtime_config["interval_minutes"]
        return doc

    @classmethod
    async def _auto_sync_loop(cls):
        assert cls._stop_event is not None
        while not cls._stop_event.is_set():
            try:
                await cls.run_sync(mode="auto")
            except Exception as exc:
                await db["HRSyncState"].update_one(
                    {"scope": cls.STATUS_SCOPE},
                    {
                        "$set": {
                            "scope": cls.STATUS_SCOPE,
                            "status": "failed",
                            "mode": "auto",
                            "error": str(exc),
                            "completed_at": cls._utc_now(),
                        }
                    },
                    upsert=True,
                )

            try:
                await asyncio.wait_for(
                    cls._stop_event.wait(),
                    timeout=max(60, (await cls.get_runtime_config())["interval_minutes"] * 60),
                )
            except asyncio.TimeoutError:
                continue

    @classmethod
    async def start_auto_sync(cls):
        runtime_config = await cls.get_runtime_config()
        if not runtime_config["auto_sync_enabled"] or cls._task is not None:
            return

        cls._stop_event = asyncio.Event()
        cls._task = asyncio.create_task(cls._auto_sync_loop())

    @classmethod
    async def stop_auto_sync(cls):
        if cls._task is None:
            return

        assert cls._stop_event is not None
        cls._stop_event.set()
        try:
            await cls._task
        finally:
            cls._task = None
            cls._stop_event = None
