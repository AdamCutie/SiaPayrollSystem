from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.database import db
from core.security import get_password_hash, verify_password
from db.models import AuthUser

AUTH_USERS_COLLECTION = "AuthUsers"


class AuthUserService:
    @classmethod
    async def get_by_email(cls, email: str) -> Optional[AuthUser]:
        collection = db[AUTH_USERS_COLLECTION]
        email = email.strip().lower()
        doc = await collection.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
        return AuthUser(**doc) if doc else None

    @classmethod
    async def verify_login_password(cls, email: str, plain_password: str) -> bool:
        auth_user = await cls.get_by_email(email)
        if not auth_user:
            return False
        return verify_password(plain_password, auth_user.password_hash)

    @classmethod
    async def upsert_password(cls, *, email: str, employee_id: str, plain_password: str) -> None:
        collection = db[AUTH_USERS_COLLECTION]
        now = datetime.now(timezone.utc)
        password_hash = get_password_hash(plain_password)

        await collection.update_one(
            {"email": email},
            {
                "$set": {
                    "employee_id": employee_id,
                    "email": email,
                    "password_hash": password_hash,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

