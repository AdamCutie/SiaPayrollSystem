from motor.motor_asyncio import AsyncIOMotorCollection
from typing import List, Optional
from datetime import datetime
from core.database import db, hr_db
from pydantic import ValidationError
from .schemas import HREmployeeRead, HRPayrollConfigRead, HRPayrollConfigUpdate
from bson import ObjectId

# 1. Define the Collection Names as they exist in the legacy DB
EMPLOYEES_COLLECTION = "Employees"
PAYROLL_CONFIG_COLLECTION = "PayrollConfigurations"
ATTENDANCE_COLLECTION = "Attendance"
LEAVES_COLLECTION = "Leaves"

# Optional fallback config storage inside the payroll DB (keeps HR DB read-only)
PAYROLL_CONFIG_OVERRIDES_COLLECTION = "PayrollConfigOverrides"

async def get_hr_attendance_count(
    employee_id_str: str, 
    employee_number: str,
    start_date: datetime, 
    end_date: datetime
) -> int:
    """
    Queries real attendance logs from the HR System database.
    Source of Truth: Legacy HR System.
    """
    collection = hr_db[ATTENDANCE_COLLECTION]
    
    # Updated to match real HR structure: 'employeeId' (human number) and 'date'
    count = await collection.count_documents({
        "employeeId": employee_number,
        "date": {"$gte": start_date, "$lte": end_date}
    })
    return count

async def get_hr_approved_leaves(employee_id_str: str, start_date: datetime, end_date: datetime) -> int:
    """
    Queries real approved leave requests from the HR System database.
    """
    collection = hr_db[LEAVES_COLLECTION]
    count = await collection.count_documents({
        "employeeId": employee_id_str,
        "startDate": {"$gte": start_date},
        "endDate": {"$lte": end_date},
        "status": "approved"
    })
    return count

async def get_hr_attendance_list(
    employee_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[dict]:
    """
    Fetches raw attendance records from the HR Database with optional date filtering.
    """
    collection = hr_db[ATTENDANCE_COLLECTION]
    query = {}
    if employee_id:
        query["employeeId"] = employee_id
        
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    cursor = collection.find(query).sort("date", -1).limit(100)
    # We convert ObjectId to str for JSON compatibility
    docs = await cursor.to_list(length=100)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs

async def get_hr_leaves_list(
    employee_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[dict]:
    """
    Fetches raw leave requests from the HR Database with optional date filtering.
    """
    collection = hr_db[LEAVES_COLLECTION]
    query = {}
    if employee_id:
        query["employeeId"] = employee_id
        
    if start_date or end_date:
        query["startDate"] = {}
        if start_date:
            query["startDate"]["$gte"] = start_date
        if end_date:
            query["startDate"]["$lte"] = end_date
            
    cursor = collection.find(query).sort("startDate", -1).limit(100)
    docs = await cursor.to_list(length=100)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs

async def update_payroll_config_override(
    employee_id_str: str,
    update_data: HRPayrollConfigUpdate
) -> bool:
    """
    Saves or updates a payroll configuration override in our local database.
    Since HR DB is read-only, we store custom salary/allowance settings here.
    """
    collection = db[PAYROLL_CONFIG_OVERRIDES_COLLECTION]
    
    # We use the employee's HR ID as the link
    query = {"employeeId": employee_id_str}
    
    # Convert Pydantic model to dict, removing None values to avoid overwriting with nulls
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return False

    update_dict["updatedAt"] = datetime.now()

    result = await collection.update_one(
        query,
        {"$set": update_dict},
        upsert=True
    )
    
    return True # If it didn't raise an exception, it succeeded in MongoDB terms.

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
        try:
            employees.append(HREmployeeRead(**doc))
        except ValidationError as e:
            doc_id = doc.get("_id", "<unknown>")
            print(f"WARNING: Skipping invalid HR employee doc _id={doc_id}: {e}")

    return employees


async def get_employee_by_email(email: str) -> Optional[HREmployeeRead]:
    """
    Fetches a single employee record from HR by email (unique in most systems).
    """
    collection = hr_db[EMPLOYEES_COLLECTION]
    doc = await collection.find_one({"email": email})
    if not doc:
        return None

    try:
        return HREmployeeRead(**doc)
    except ValidationError as e:
        doc_id = doc.get("_id", "<unknown>")
        print(f"WARNING: HR employee record invalid for _id={doc_id}: {e}")
        return None


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
    if not doc:
        return None

    try:
        return HREmployeeRead(**doc)
    except ValidationError as e:
        doc_id = doc.get("_id", "<unknown>")
        print(f"WARNING: HR employee record invalid for _id={doc_id}: {e}")
        return None


async def get_employee_payroll_config(
    employee_id_str: str,
    employee_number: str,
    full_name: str
) -> Optional[HRPayrollConfigRead]:
    """
    Fetches the LATEST salary settings for an employee.
    PRIORITY:
    1. Local Payroll Database (Overrides from our UI)
    2. Legacy HR System (Default values)
    """
    
    # --- 1. CHECK LOCAL OVERRIDES FIRST ---
    override_terms: list[dict] = []
    if employee_id_str:
        override_terms.append({"employeeId": employee_id_str})
        if ObjectId.is_valid(employee_id_str):
            override_terms.append({"employeeId": ObjectId(employee_id_str)})
    if employee_number:
        override_terms.append({"employeeNumber": employee_number})

    if override_terms:
        override_cursor = db[PAYROLL_CONFIG_OVERRIDES_COLLECTION].find({"$or": override_terms}).sort("updatedAt", -1).limit(1)
        override_docs = await override_cursor.to_list(length=1)
        if override_docs:
            try:
                return HRPayrollConfigRead(**override_docs[0])
            except ValidationError as e:
                print(f"WARNING: Invalid local override doc: {e}")

    # --- 2. FALLBACK TO HR SYSTEM ---
    collection = hr_db[PAYROLL_CONFIG_COLLECTION]
    or_terms: list[dict] = []

    if employee_id_str:
        or_terms.append({"employeeId": employee_id_str})
        if ObjectId.is_valid(employee_id_str):
            or_terms.append({"employeeId": ObjectId(employee_id_str)})
    if employee_number:
        or_terms.append({"employeeNumber": employee_number})
    if full_name:
        last_name = full_name.split(",")[0].strip().replace(" ", "")
        if len(last_name) >= 2:
            or_terms.append({"employeeName": {"$regex": f"^{last_name[:4]}", "$options": "i"}})

    if not or_terms:
        return None

    cursor = collection.find({"$or": or_terms}).sort("updatedAt", -1).limit(1)
    docs = await cursor.to_list(length=1)
    
    if docs:
        try:
            return HRPayrollConfigRead(**docs[0])
        except ValidationError as e:
            print(f"WARNING: Invalid HR payroll config: {e}")
            return None

    return None
