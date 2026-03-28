from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from core.config import settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/payroll/auth/login", auto_error=False)


class TokenPayload(BaseModel):
    sub: str  # email
    role: str  # "admin" | "employee"
    employee_id: str  # HR Employee._id (stringified ObjectId)
    exp: int | None = None


class CurrentUser(BaseModel):
    email: str
    role: str
    employee_id: str


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_payload(token: str | None = Depends(oauth2_scheme)) -> TokenPayload:
    if settings.DISABLE_AUTH:
        return TokenPayload(sub="dev@local", role="admin", employee_id="dev", exp=None)

    if not token:
        raise _unauthorized()

    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return TokenPayload(**decoded)
    except (JWTError, ValidationError):
        raise _unauthorized()


async def get_current_user(payload: TokenPayload = Depends(get_token_payload)) -> CurrentUser:
    return CurrentUser(email=payload.sub, role=payload.role, employee_id=payload.employee_id)


def require_roles(*allowed_roles: str):
    async def _require(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _require


require_user = require_roles("admin", "employee")
require_admin = require_roles("admin")
