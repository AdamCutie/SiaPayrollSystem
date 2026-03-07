from motor.motor_asyncio import AsyncIOMotorCollection
from typing import List, Optional
from core.database import hr_db
from .schemas import HREmployeeRead, HRPayrollConfigRead

# 1. Define the Collection Names as they exist in the legacy DB
EMPLOYEES_COLLECTION = "Employees"
PAYROLL_CONFIG_COLLECTION = "PayrollConfiguration"


async def get_all_active_employees() -> List[HREmployeeRead]:
    """
    Fetches all employees from the legacy HR system who are marked as active.
    """

    # Access the 'Employees' collection in the legacy HR database
    collection = hr_db[EMPLOYEES_COLLECTION]

    # Query: Find all documents where isActive is true
    cursor = collection.find({"isActive": True})

    employees: List[HREmployeeRead] = []

    async for doc in cursor:
        # Convert MongoDB document into a Pydantic schema
        employees.append(HREmployeeRead(**doc))

    return employees


async def get_employee_payroll_config(
    employee_id_str: str,
) -> Optional[HRPayrollConfigRead]:
    """
    Fetches the salary and deduction settings for a specific employee.

    Note:
        employee_id_str is the MongoDB _id of the employee.
    """

    collection = hr_db[PAYROLL_CONFIG_COLLECTION]

    # Query: Find the config linked to this specific employee _id
    # In the legacy system, this is stored as a string in 'employeeId'
    doc = await collection.find_one({
        "employeeId": employee_id_str,
        "isActive": True
    })

    if doc:
        return HRPayrollConfigRead(**doc)

    return None
