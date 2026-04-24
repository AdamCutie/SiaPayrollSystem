from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from core.auth import CurrentUser, get_current_user
from core.auth import require_admin
from core.config import settings
from core.security import create_access_token
from core.database import db
from integrations.hr.adapter import SYNCED_HR_EMPLOYEES_COLLECTION
from .service import AuthUserService

router = APIRouter(prefix="/auth", tags=["Security & Authentication"])

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    employee_id: str

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Standard OAuth2 Login.
    In this system, we check our local synced HR 'email' field.

    Passwords are stored in the payroll database (AuthUsers) to keep the HR DB read-only.
    If ALLOW_PASSWORDLESS_LOGIN is enabled, users without a password record can still log in (dev-only).
    """
    hr_coll = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    # 1. Find user by email in our synced mirror (case-insensitive)
    username = form_data.username.strip().lower()
    sync_doc = await hr_coll.find_one({"payload.email": {"$regex": f"^{username}$", "$options": "i"}})
    
    if not sync_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = sync_doc.get("payload", {})
    email = user.get("email", "")
    employee_id = str(sync_doc.get("_id", ""))

    # 2. Check Role (Admin vs Employee)
    hr_role = str(user.get("role", "")).strip()
    normalized_hr_role = hr_role.casefold()
    normalized_admin_roles = {r.strip().casefold() for r in settings.HR_ADMIN_ROLES}
    role = "admin" if normalized_hr_role in normalized_admin_roles else "employee"

    # 3. Verify Password (from payroll DB credentials store)
    auth_user = await AuthUserService.get_by_email(email)
    if auth_user:
        ok = await AuthUserService.verify_login_password(email, form_data.password)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif not settings.ALLOW_PASSWORDLESS_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is not set for this account. Ask an admin to set it.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Create Token
    access_token = create_access_token(
        data={"sub": email, "role": role, "employee_id": employee_id}
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": role,
        "employee_id": employee_id
    }


@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """
    Debug helper: returns the currently authenticated user info from the JWT.
    Useful for diagnosing 401 vs 403 issues.
    """
    return user


class SetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/set-password")
async def set_password(request: SetPasswordRequest, _: object = Depends(require_admin)):
    """
    Admin-only: sets/updates a user's password in the payroll DB (AuthUsers).
    The user must exist in our synced HR Employees mirror.
    """
    hr_coll = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    sync_doc = await hr_coll.find_one({"payload.email": str(request.email)})
    if not sync_doc:
        raise HTTPException(status_code=404, detail="HR user not found for the given email.")

    user = sync_doc.get("payload", {})
    await AuthUserService.upsert_password(
        email=str(request.email),
        employee_id=str(sync_doc.get("_id", "")),
        plain_password=request.new_password,
    )
    return {"message": "Password set successfully."}
