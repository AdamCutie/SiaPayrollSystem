from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId

# Custom type to handle Mongodb ObjectId in Pydantic


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return str(v)

# The Core Payroll Record Model


class PayrollSnapshot(BaseModel):
    """
    The 'Receipt' of a payroll calculation.
    Stored in OUR new database (not the legacy HR one).
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # Link & Identifiers
    employee_id: str  # The original MongoDB _id from the HR system
    employee_number: str  # e.g., "23-2450"
    full_name: str

    # Financial Data (The valies at the time of processing)
    basic_salary: float
    gross_pay: float
    total_deductions: float
    net_pay: float

    # Payroll Metadata
    pay_period_start: datetime
    pay_period_end: datetime
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "Completed"

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
