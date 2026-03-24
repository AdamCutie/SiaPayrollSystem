from motor.motor_asyncio import AsyncIOMotorCollection
from typing import List, Optional
from core.database import db, hr_db
from .schemas import HREmployeeRead, HRPayrollConfigRead
from bson import ObjectId

# 1. Define the Collection Names as they exist in the legacy DB
EMPLOYEES_COLLECTION = "Employees"
PAYROLL_CONFIG_COLLECTION = "PayrollConfigurations"
# Optional fallback config storage inside the payroll DB (keeps HR DB read-only)
PAYROLL_CONFIG_OVERRIDES_COLLECTION = "PayrollConfigOverrides"


async def get_all_active_employees(limit: int | None = None) -> List[HREmployeeRead]:
    """
    Fetches all employees from the legacy HR system who are marked as active.
    """
    collection = hr_db[EMPLOYEES_COLLECTION]
    cursor = collection.find({"isActive": True})
    if limit is not None:
        cursor = cursor.limit(limit)

    employees: List[HREmployeeRead] = []
    async for doc in cursor:
        employees.append(HREmployeeRead(**doc))

    return employees


async def get_employee_by_email(email: str) -> Optional[HREmployeeRead]:
    """
    Fetches a single employee record from HR by email (unique in most systems).
    """
    collection = hr_db[EMPLOYEES_COLLECTION]
    doc = await collection.find_one({"email": email})
    return HREmployeeRead(**doc) if doc else None


async def get_employee_by_id(employee_id_str: str) -> Optional[HREmployeeRead]:
    """
    Fetches a single employee record from HR by MongoDB _id (preferred) or employeeId (employee number).
    """
    collection = hr_db[EMPLOYEES_COLLECTION]

    or_terms: list[dict] = []
    if employee_id_str and ObjectId.is_valid(employee_id_str):
        or_terms.append({"_id": ObjectId(employee_id_str)})

    if employee_id_str:
        # Some systems pass the human employee number instead of MongoDB _id.
        or_terms.append({"employeeId": employee_id_str})

    if not or_terms:
        return None

    doc = await collection.find_one({"$or": or_terms})
    return HREmployeeRead(**doc) if doc else None


async def get_employee_payroll_config(
    employee_id_str: str,
    employee_number: str,
    full_name: str
) -> Optional[HRPayrollConfigRead]:
    """
    Fetches the LATEST salary settings for an employee.
    Uses sorting to handle legacy systems that store multiple historical salary records.
    """
    collection = hr_db[PAYROLL_CONFIG_COLLECTION]

    # Multi-key search for maximum compatibility (legacy DBs are often inconsistent).
    # IMPORTANT: only include filters when we have real values, otherwise we risk matching the wrong employee.
    or_terms: list[dict] = []

    if employee_id_str:
        or_terms.append({"employeeId": employee_id_str})
        if ObjectId.is_valid(employee_id_str):
            or_terms.append({"employeeId": ObjectId(employee_id_str)})

    if employee_number:
        or_terms.append({"employeeNumber": employee_number})

    if full_name:
        # Clean the name for fuzzy matching (handling spaces)
        last_name = full_name.split(",")[0].strip().replace(" ", "")
        # Avoid a dangerous "match everything" regex like "^" when last_name is empty.
        if len(last_name) >= 2:
            or_terms.append({"employeeName": {"$regex": f"^{last_name[:4]}", "$options": "i"}})

    if not or_terms:
        return None

    query = {"$or": or_terms}

    # Sort by 'updatedAt' descending to get the most recent salary configuration
    cursor = collection.find(query).sort("updatedAt", -1).limit(1)
    
    docs = await cursor.to_list(length=1)
    
    if docs:
        return HRPayrollConfigRead(**docs[0])

    # If HR has no payroll configuration, fall back to payroll DB overrides (dev/test support).
    override_terms: list[dict] = []
    if employee_id_str:
        override_terms.append({"employeeId": employee_id_str})
        if ObjectId.is_valid(employee_id_str):
            override_terms.append({"employeeId": ObjectId(employee_id_str)})

    if employee_number:
        override_terms.append({"employeeNumber": employee_number})

    if not override_terms:
        return None

    override_query = {"$or": override_terms}
    override_cursor = db[PAYROLL_CONFIG_OVERRIDES_COLLECTION].find(override_query).sort("updatedAt", -1).limit(1)
    override_docs = await override_cursor.to_list(length=1)
    if override_docs:
        return HRPayrollConfigRead(**override_docs[0])

    return None
