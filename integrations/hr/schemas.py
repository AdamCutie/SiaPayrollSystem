from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from bson import ObjectId

# Helper to handle MongoDB ObjectIds in Pydantic


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return str(v)


class HREmployeeRead(BaseModel):
    """Schema for reading basic employee data from legacy
      HR DB"""
    id: PyObjectId = Field(alias="_id")
    employeeId: str  # e.g., "23-2211"
    firstName: str
    lastName: str
    email: EmailStr
    department: str
    role: str
    isActive: bool

    class Config:
        populated_by_name = True
        json_encoders = {ObjectId: str}


class HRPayrollConfigRead(BaseModel):
    """Schema for reading salary configurations from
      legacy HR DB"""
    id: PyObjectId = Field(alias="_id")
    employeeId: str  # Links to Employee._id
    basicSalary: float

    # Allowances
    housingAllowance: float = 0.0
    trasportAllowance: float = 0.0
    mealAllowance: float = 0.0
    otherAllowance: float = 0.0

    # Statutory Deductions
    sssContribution: float = 0.0
    philHealthContribution: float = 0.0
    pagIbigContribution: float = 0.0
    withholdingTax: float = 0.0

    # Loans
    sssloan: float = 0.0
    pagIbigloan: float = 0.0
    companyloan: float = 0.0

    # Penalty Rates
    absencePenaltyRate: float = 0.0
    latePenaltyRate: float = 0.0

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
