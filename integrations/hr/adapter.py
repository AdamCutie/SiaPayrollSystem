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
    Fetches the LATEST salary settings for an employee.
    Uses sorting to handle legacy systems that store multiple historical salary records.
    """
    collection = hr_db[PAYROLL_CONFIG_COLLECTION]

    # Clean the name for fuzzy matching (handling spaces)
    last_name = full_name.split(',')[0].strip().replace(" ", "")

    # Multi-key search for maximum compatibility
    query = {
        "$or": [
            {"employeeId": employee_id_str},
            {"employeeId": ObjectId(employee_id_str) if ObjectId.is_valid(employee_id_str) else None},
            {"employeeNumber": employee_number},
            {"employeeName": {"$regex": f"^{last_name[:4]}", "$options": "i"}}
        ]
    }

    # Sort by 'updatedAt' descending to get the most recent salary configuration
    cursor = collection.find(query).sort("updatedAt", -1).limit(1)
    
    docs = await cursor.to_list(length=1)
    
    if docs:
        return HRPayrollConfigRead(**docs[0])

    return None
