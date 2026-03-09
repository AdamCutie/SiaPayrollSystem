from motor.motor_asyncio import AsyncIOMotorCollection
from typing import List, Optional
from core.database import hr_db
from .schemas import HREmployeeRead, HRPayrollConfigRead
from bson import ObjectId

# 1. Define the Collection Names as they exist in the legacy DB
EMPLOYEES_COLLECTION = "Employees"
PAYROLL_CONFIG_COLLECTION = "PayrollConfigurations"


async def get_all_active_employees() -> List[HREmployeeRead]:
    """
    Fetches all employees from the legacy HR system who are marked as active.
    """
    collection = hr_db[EMPLOYEES_COLLECTION]
    cursor = collection.find({"isActive": True})

    employees: List[HREmployeeRead] = []
    async for doc in cursor:
        employees.append(HREmployeeRead(**doc))

    return employees


async def get_employee_payroll_config(
    employee_id_str: str,
    employee_number: str,
    full_name: str
) -> Optional[HRPayrollConfigRead]:
    """
    Aggressive search for salary settings using ID, Number, or Name.
    Improved fuzzy search to handle spaces in legacy name data.
    """
    collection = hr_db[PAYROLL_CONFIG_COLLECTION]

    # Clean the last name for searching (e.g., "Dela Cruz" -> "DelaCruz")
    # We use a fuzzy regex to bridge the gap between "Dela Cruz" and "Delacruz"
    last_name = full_name.split(',')[0].strip().replace(" ", "")

    query = {
        "$or": [
            {"employeeId": employee_id_str},
            {"employeeId": ObjectId(employee_id_str) if ObjectId.is_valid(employee_id_str) else None},
            {"employeeNumber": employee_number},
            # Fuzzy match: Look for the start of the surname, ignoring case
            {"employeeName": {"$regex": f"^{last_name[:4]}", "$options": "i"}}
        ]
    }

    doc = await collection.find_one(query)
    if doc:
        return HRPayrollConfigRead(**doc)

    return None
