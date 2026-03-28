from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from core.auth import CurrentUser, get_current_user
from core.auth import require_admin
from core.config import settings
from core.security import create_access_token
from core.database import hr_db
from integrations.hr.adapter import EMPLOYEES_COLLECTION
from .service import AuthUserService

router = APIRouter(prefix="/auth", tags=["Security & Authentication"])

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Standard OAuth2 Login.
    In this system, we check the legacy HR system's 'email' field.

    Passwords are stored in the payroll database (AuthUsers) to keep the HR DB read-only.
    If ALLOW_PASSWORDLESS_LOGIN is enabled, users without a password record can still log in (dev-only).
    """
    hr_coll = hr_db[EMPLOYEES_COLLECTION]
    # 1. Find user by email (from legacy system)
    user = await hr_coll.find_one({"email": form_data.username})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = user.get("email", "")
    employee_id = str(user.get("_id", ""))

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
        "role": role
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
    The user must exist in the legacy HR Employees collection.
    """
    hr_coll = hr_db[EMPLOYEES_COLLECTION]
    hr_user = await hr_coll.find_one({"email": str(request.email)})
    if not hr_user:
        raise HTTPException(status_code=404, detail="HR user not found for the given email.")

    await AuthUserService.upsert_password(
        email=str(request.email),
        employee_id=str(hr_user.get("_id", "")),
        plain_password=request.new_password,
    )
    return {"message": "Password set successfully."}
