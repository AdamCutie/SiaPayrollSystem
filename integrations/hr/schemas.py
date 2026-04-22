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
    middleName: Optional[str] = None
    lastName: str
    email: EmailStr
    contactNo: Optional[str] = None
    address: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    age: Optional[int] = None
    birthDate: Optional[datetime] = None
    gender: Optional[str] = None
    civilStatus: Optional[str] = None
    department: str
    role: str
    position: Optional[str] = None
    isActive: bool
    contractType: str = "Provisionary" # "Regular" or "Provisionary"
    baseSalary: Money = 0.0 # Discovered directly in Employees collection
    hiredDate: Optional[datetime] = None
    applicantId: Optional[PyObjectId] = None
    sssNumber: Optional[str] = None
    philHealthNumber: Optional[str] = None
    pagIbigNumber: Optional[str] = None
    resignationStatus: Optional[str] = None
    resignationDate: Optional[datetime] = None
    resignationReason: Optional[str] = None

class HRRoleSalaryRead(BaseModel):
    """Schema for reading role-based salaries from synced HR DB"""
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: PyObjectId = Field(alias="_id")
    roleName: str
    department: str
    baseSalary: Money
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
    sssEmployeeShare: Money = 0.0
    sssEmployerShare: Money = 0.0
    sssECEmployer: Money = 0.0
    sssMPFEmployeeShare: Money = 0.0
    sssMPFEmployerShare: Money = 0.0
    sssMonthlySalaryCredit: Money = 0.0
    philHealthContribution: Money = 0.0
    pagIbigContribution: Money = 0.0
    withholdingTax: Money = 0.0

    sssLoan: Money = 0.0
    pagIbigLoan: Money = 0.0
    companyLoan: Money = 0.0

    absencePenaltyRate: Money = 0.0
    latePenaltyRate: Money = 0.0

class HRPayrollConfigUpdate(BaseModel):
    """Schema for updating/overriding payroll configurations."""
    basicSalary: Optional[float] = None
    housingAllowance: Optional[float] = None
    transportAllowance: Optional[float] = None
    mealAllowance: Optional[float] = None
    otherAllowances: Optional[float] = None

    pagIbigContribution: Optional[float] = None
    withholdingTax: Optional[float] = None

    sssLoan: Optional[float] = None
    pagIbigLoan: Optional[float] = None
    companyLoan: Optional[float] = None

    absencePenaltyRate: Optional[float] = None
    latePenaltyRate: Optional[float] = None
