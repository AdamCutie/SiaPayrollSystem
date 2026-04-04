from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from core.auth import CurrentUser
from core.database import db, hr_db
from db.models import ActivityLog
from integrations.hr.adapter import get_employee_by_id, get_synced_employee_by_id


LOCAL_ACTIVITY_COLLECTION = "ActivityLogs"
HR_ACTIVITY_COLLECTION = "ActivityLogs"


class ActivityLogService:
    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return ActivityLogService._utc_now()
        return ActivityLogService._utc_now()

    @staticmethod
    async def _resolve_actor_name(user: Optional[CurrentUser]) -> str:
        if not user:
            return "System"

        employee = await get_synced_employee_by_id(user.employee_id)
        if not employee:
            employee = await get_employee_by_id(user.employee_id)

        if employee:
            return f"{employee.firstName} {employee.lastName}".strip()

        return user.email or user.employee_id or "System"

    @classmethod
    async def log_local_activity(
        cls,
        *,
        module: str,
        action: str,
        target_info: str = "",
        user: Optional[CurrentUser] = None,
        actor_name: Optional[str] = None,
        visibility: str = "HR & Payroll",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        resolved_actor_name = actor_name or await cls._resolve_actor_name(user)
        entry = ActivityLog(
            module=module,
            action=action,
            targetInfo=target_info,
            actorName=resolved_actor_name,
            actorEmail=user.email if user else None,
            actorEmployeeId=user.employee_id if user else None,
            actorRole=user.role if user else None,
            visibility=visibility,
            metadata=metadata or {},
        )
        payload = entry.model_dump(by_alias=True, exclude={"id"})
        result = await db[LOCAL_ACTIVITY_COLLECTION].insert_one(payload)
        payload["_id"] = str(result.inserted_id)
        return payload

    @classmethod
    def _normalize_hr_log(cls, doc: dict) -> dict:
        timestamp = cls._normalize_datetime(doc.get("timestamp"))
        return {
            "_id": str(doc.get("_id")),
            "source": "hr",
            "module": doc.get("module") or "HR",
            "action": doc.get("action") or "HR Activity",
            "targetInfo": doc.get("targetInfo") or "",
            "actorName": doc.get("hrName") or doc.get("hrUsername") or "HR",
            "actorEmail": None,
            "actorEmployeeId": doc.get("hrUsername"),
            "actorRole": "admin",
            "visibility": "HR & Payroll",
            "metadata": {},
            "timestamp": timestamp.isoformat(),
        }

    @classmethod
    def _normalize_local_log(cls, doc: dict) -> dict:
        timestamp = cls._normalize_datetime(doc.get("timestamp"))
        normalized = {
            "_id": str(doc.get("_id")),
            "source": doc.get("source", "payroll"),
            "module": doc.get("module") or "Payroll",
            "action": doc.get("action") or "System Activity",
            "targetInfo": doc.get("targetInfo") or "",
            "actorName": doc.get("actorName") or "System",
            "actorEmail": doc.get("actorEmail"),
            "actorEmployeeId": doc.get("actorEmployeeId"),
            "actorRole": doc.get("actorRole"),
            "visibility": doc.get("visibility") or "HR & Payroll",
            "metadata": doc.get("metadata") or {},
            "timestamp": timestamp.isoformat(),
        }
        return normalized

    @classmethod
    async def get_combined_activity_logs(
        cls,
        *,
        limit: int = 100,
        source: Optional[str] = None,
        period: str = "today",
    ) -> list[dict]:
        safe_limit = max(1, min(limit, 500))

        hr_logs: list[dict] = []
        local_logs: list[dict] = []

        # Time range filter
        filter_query = {}
        now = datetime.now(timezone.utc)
        
        if period != "all":
            start_date = None
            if period == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "yesterday":
                start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                filter_query["timestamp"] = {"$gte": start_date, "$lt": end_date}
            elif period == "week":
                start_date = now - timedelta(days=7)
            elif period == "month":
                start_date = now - timedelta(days=30)
            
            if start_date and period != "yesterday":
                filter_query["timestamp"] = {"$gte": start_date}

        if source in (None, "all", "hr"):
            hr_docs = await hr_db[HR_ACTIVITY_COLLECTION].find(filter_query).sort("timestamp", -1).limit(safe_limit).to_list(length=safe_limit)
            hr_logs = [cls._normalize_hr_log(doc) for doc in hr_docs]

        if source in (None, "all", "payroll"):
            local_docs = await db[LOCAL_ACTIVITY_COLLECTION].find(filter_query).sort("timestamp", -1).limit(safe_limit).to_list(length=safe_limit)
            local_logs = [cls._normalize_local_log(doc) for doc in local_docs]

        combined = hr_logs + local_logs
        combined.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        return combined[:safe_limit]
