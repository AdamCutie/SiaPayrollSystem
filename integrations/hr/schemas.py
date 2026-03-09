from pydantic import BaseModel, Field, EmailStr, ConfigDict, BeforeValidator
from typing import Optional, Annotated, Any
from datetime import datetime
from bson import ObjectId, Decimal128

# 1. ID Helper
PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]

# 2. Money Helper (Improved to handle Decimal128, floats, and ints safely)
Money = Annotated[float, BeforeValidator(
    lambda v: float(v.to_decimal()) if hasattr(v, 'to_decimal') else float(v)
)]

class HREmployeeRead(BaseModel):
    """Schema for reading basic employee data from legacy HR DB"""
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: PyObjectId = Field(alias="_id")
    employeeId: str  # e.g., "23-2211"
    firstName: str
    lastName: str
    email: EmailStr
    department: str
    role: str
    isActive: bool

class HRPayrollConfigRead(BaseModel):
    """Schema for reading salary configurations from legacy HR DB"""
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: PyObjectId = Field(alias="_id")
    employeeId: str  # Links to Employee._id
    
    # Using 'Money' helper to handle MongoDB Decimal128 types
    basicSalary: Money
    housingAllowance: Money = 0.0
    transportAllowance: Money = 0.0
    mealAllowance: Money = 0.0
    otherAllowances: Money = 0.0

    sssContribution: Money = 0.0
    philHealthContribution: Money = 0.0
    pagIbigContribution: Money = 0.0
    withholdingTax: Money = 0.0

    sssLoan: Money = 0.0
    pagIbigLoan: Money = 0.0
    companyLoan: Money = 0.0

    absencePenaltyRate: Money = 0.0
    latePenaltyRate: Money = 0.0
