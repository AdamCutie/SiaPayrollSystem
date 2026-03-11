from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from core.security import verify_password, create_access_token, get_password_hash
from core.database import hr_db
from integrations.hr.adapter import EMPLOYEES_COLLECTION
from pydantic import BaseModel

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
    Note: Legacy passwords would need to be migrated/set for this to work.
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

    # 2. Check Role (Admin vs Employee)
    role = "admin" if user.get("role") == "HR Admin" else "employee"

    # 3. Create Token
    access_token = create_access_token(
        data={"sub": user["email"], "role": role}
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": role
    }
