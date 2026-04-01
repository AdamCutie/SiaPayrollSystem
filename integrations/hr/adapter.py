from motor.motor_asyncio import AsyncIOMotorCollection
from typing import List, Optional
from datetime import datetime, date, timedelta
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
SYNCED_HR_EMPLOYEES_COLLECTION = "SyncedHREmployees"
SYNCED_HR_PAYROLL_CONFIG_COLLECTION = "SyncedHRPayrollConfigurations"
SYNCED_HR_ATTENDANCE_COLLECTION = "SyncedHRAttendance"
SYNCED_HR_LEAVES_COLLECTION = "SyncedHRLeaves"
SYNCED_HR_OVERTIME_REQUESTS_COLLECTION = "SyncedHROvertimeRequests"

async def get_hr_attendance_count(
    employee_id_str: str, 
    employee_number: str,
    start_date: datetime, 
    end_date: datetime
) -> int:
    """
    Queries real attendance logs from the HR System database.
    Handles both String-based and Object-based dates.
    """
    collection = hr_db[ATTENDANCE_COLLECTION]
    
    # Formats for query
    s_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
    e_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")

    # UNIVERSAL QUERY: Check both Date Objects AND Strings
    query = {
        "employeeId": employee_number,
        "$or": [
            {"date": {"$gte": start_date, "$lte": end_date}}, # For BSON Date objects
            {"date": {"$gte": s_str, "$lte": e_str}}          # For ISO Strings
        ]
    }

    count = await collection.count_documents(query)
    return count

async def get_hr_approved_leaves(employee_id_str: str, start_date: datetime, end_date: datetime) -> int:
    """
    Queries real approved leave requests from the HR System database.
    """
    collection = hr_db[LEAVES_COLLECTION]
    
    s_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
    e_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")

    count = await collection.count_documents({
        "employeeId": employee_id_str,
        "startDate": {"$gte": s_str},
        "endDate": {"$lte": e_str},
        "status": {"$regex": "^approved$", "$options": "i"}
    })
    return count

def _build_hr_date_query(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Optional[dict]:
    if not (start_date and end_date):
        return None

    s_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
    e_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "$or": [
            {"date": {"$gte": start_date, "$lte": end_date}},
            {"date": {"$gte": s_str, "$lte": e_str}},
        ]
    }


def _parse_hr_datetime(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.fromisoformat(value.split("T")[0])
            except ValueError:
                return None
    return None


def _iter_overlapping_dates(start_dt: datetime, end_dt: datetime, range_start: datetime, range_end: datetime):
    overlap_start = max(range_start.date(), start_dt.date())
    overlap_end = min(range_end.date(), end_dt.date())
    if overlap_end < overlap_start:
        return

    cursor = overlap_start
    while cursor <= overlap_end:
        yield cursor
        cursor += timedelta(days=1)

async def get_hr_attendance_list(
    employee_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[dict]:
    """
    Fetches raw attendance logs from the HR System.
    Enriches with Employee Name.
    """
    collection = hr_db[ATTENDANCE_COLLECTION]
    query = {}
    if employee_id:
        query["employeeId"] = employee_id

    date_query = _build_hr_date_query(start_date, end_date)
    if date_query:
        query.update(date_query)

    cursor = collection.find(query).sort("date", -1).limit(1000)
    docs = await cursor.to_list(length=1000)
    
    # Enrich with Name
    enriched = []
    emp_cache = {}
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        eid = doc.get("employeeId")
        if eid not in emp_cache:
            emp = await hr_db[EMPLOYEES_COLLECTION].find_one({"employeeId": eid})
            if emp:
                emp_cache[eid] = f"{emp.get('lastName')}, {emp.get('firstName')}"
            else:
                emp_cache[eid] = f"Unknown ({eid})"
        
        doc["employeeName"] = emp_cache[eid]
        enriched.append(doc)
    return enriched

async def get_hr_leaves_list(
    employee_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    approved_only: bool = False,
) -> List[dict]:
    """
    Fetches raw leave requests from the HR Database with optional date filtering.
    Handles both String and Object dates.
    Enriches with Employee Name.
    """
    collection = hr_db[LEAVES_COLLECTION]
    query = {}
    if employee_id:
        query["employeeId"] = employee_id

    if approved_only:
        query["status"] = {"$regex": "^approved$", "$options": "i"}
        
    if start_date and end_date:
        s_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
        e_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
        query["$or"] = [
            {"startDate": {"$gte": start_date}, "endDate": {"$lte": end_date}},
            {"startDate": {"$gte": s_str}, "endDate": {"$lte": e_str}}
        ]
            
    cursor = collection.find(query).sort("startDate", -1).limit(100)
    docs = await cursor.to_list(length=100)
    
    # Enrich with FullName
    enriched_docs = []
    emp_cache = {} # Cache names to avoid redundant DB hits
    
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        
        # Try different ID keys used in HR DB
        eid = doc.get("employeeId") or doc.get("employee_id") or doc.get("empId")
        
        if eid and eid not in emp_cache:
            # Normalize ID: remove spaces and ensure string
            clean_eid = str(eid).strip()
            
            # Search by the human employee number
            emp = await hr_db[EMPLOYEES_COLLECTION].find_one({"employeeId": clean_eid})
            if emp:
                emp_cache[eid] = f"{emp.get('lastName')}, {emp.get('firstName')}"
            else:
                # If not found, it's likely an employee from a previous year (e.g., 2025)
                emp_cache[eid] = f"Archived/Inactive ({eid})"
        
        doc["fullName"] = emp_cache.get(eid, "Unknown")
        enriched_docs.append(doc)
        
    return enriched_docs


async def get_hr_approved_leave_days(
    employee_number: str,
    start_date: datetime,
    end_date: datetime,
) -> int:
    """
    Counts approved HR leave days overlapping the payroll period.
    Uses the human employee number because HR leave/attendance data is keyed that way.
    """
    if not employee_number:
        return 0

    approved_leaves = await get_hr_leaves_list(
        employee_id=employee_number,
        start_date=start_date,
        end_date=end_date,
        approved_only=True,
    )

    total_days = 0
    for doc in approved_leaves:
        start_dt = _parse_hr_datetime(doc.get("startDate"))
        end_dt = _parse_hr_datetime(doc.get("endDate"))
        if not start_dt or not end_dt:
            continue

        overlap_start = max(start_date.date(), start_dt.date())
        overlap_end = min(end_date.date(), end_dt.date())
        if overlap_end < overlap_start:
            continue

        total_days += (overlap_end - overlap_start).days + 1

    return total_days


async def get_hr_approved_leave_dates(
    employee_number: str,
    start_date: datetime,
    end_date: datetime,
) -> set[date]:
    """
    Returns approved HR leave dates overlapping the payroll period.
    The caller decides which of those dates count for payroll.
    """
    if not employee_number:
        return set()

    approved_leaves = await get_hr_leaves_list(
        employee_id=employee_number,
        start_date=start_date,
        end_date=end_date,
        approved_only=True,
    )

    leave_dates: set[date] = set()
    for doc in approved_leaves:
        start_dt = _parse_hr_datetime(doc.get("startDate"))
        end_dt = _parse_hr_datetime(doc.get("endDate"))
        if not start_dt or not end_dt:
            continue

        for leave_day in _iter_overlapping_dates(start_dt, end_dt, start_date, end_date):
            leave_dates.add(leave_day)

    return leave_dates

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


async def get_synced_active_employees(limit: int | None = None) -> List[HREmployeeRead]:
    collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    cursor = collection.find({"payload.isActive": True})
    if limit is not None:
        cursor = cursor.limit(limit)

    employees: List[HREmployeeRead] = []
    async for doc in cursor:
        payload = doc.get("payload", {})
        try:
            employees.append(HREmployeeRead(**payload))
        except ValidationError as e:
            doc_id = doc.get("_id", "<unknown>")
            print(f"WARNING: Skipping invalid synced HR employee doc _id={doc_id}: {e}")

    return employees


async def get_synced_employee_by_id(employee_id_str: str) -> Optional[HREmployeeRead]:
    collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]

    or_terms: list[dict] = []
    if employee_id_str:
        or_terms.append({"payload.employeeId": employee_id_str})
        or_terms.append({"payload._id": employee_id_str})

    if not or_terms:
        return None

    doc = await collection.find_one({"$or": or_terms})
    if not doc:
        return None

    try:
        return HREmployeeRead(**doc.get("payload", {}))
    except ValidationError as e:
        doc_id = doc.get("_id", "<unknown>")
        print(f"WARNING: Synced HR employee record invalid for _id={doc_id}: {e}")
        return None


async def _get_synced_employee_name_map(employee_numbers: set[str]) -> dict[str, str]:
    if not employee_numbers:
        return {}

    collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    docs = await collection.find({"payload.employeeId": {"$in": list(employee_numbers)}}).to_list(length=None)

    names: dict[str, str] = {}
    for doc in docs:
        payload = doc.get("payload", {})
        employee_number = str(payload.get("employeeId", "")).strip()
        if not employee_number:
            continue
        first_name = payload.get("firstName", "")
        last_name = payload.get("lastName", "")
        names[employee_number] = f"{last_name}, {first_name}".strip(", ")

    return names


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
    2. Legacy HR System (Specialized PayrollConfigurations table)
    3. Legacy HR System (Fallback: 'baseSalary' directly from Employees table)
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

    # --- 2. TRY HR SPECIALIZED SALARY TABLE ---
    collection = hr_db[PAYROLL_CONFIG_COLLECTION]
    or_terms: list[dict] = []

    if employee_id_str:
        or_terms.append({"employeeId": employee_id_str})
        if ObjectId.is_valid(employee_id_str):
            or_terms.append({"employeeId": ObjectId(employee_id_str)})
    if employee_number:
        # Search by both possible keys in legacy DB
        or_terms.append({"employeeNumber": employee_number})
        or_terms.append({"employeeId": employee_number})
    if full_name:
        last_name = full_name.split(",")[0].strip().replace(" ", "")
        if len(last_name) >= 2:
            or_terms.append({"employeeName": {"$regex": f"^{last_name[:4]}", "$options": "i"}})

    if or_terms:
        cursor = collection.find({"$or": or_terms}).sort("updatedAt", -1).limit(1)
        docs = await cursor.to_list(length=1)
        
        if docs:
            try:
                return HRPayrollConfigRead(**docs[0])
            except ValidationError as e:
                print(f"WARNING: Invalid HR payroll config: {e}")

    # --- 3. FALLBACK: USE 'baseSalary' FROM EMPLOYEES TABLE ---
    # This is critical for the new 2026 employees who don't have a Salary table record yet.
    emp_record = await get_employee_by_id(employee_id_str)
    if emp_record and emp_record.baseSalary > 0:
        return HRPayrollConfigRead(
            id=emp_record.id, # Dummy id for the schema
            employeeId=emp_record.employeeId,
            basicSalary=emp_record.baseSalary,
            housingAllowance=0.0,
            transportAllowance=0.0,
            mealAllowance=0.0,
            otherAllowances=0.0
        )

    return None


async def get_synced_employee_payroll_config(
    employee_id_str: str,
    employee_number: str,
    full_name: str
) -> Optional[HRPayrollConfigRead]:
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

    collection = db[SYNCED_HR_PAYROLL_CONFIG_COLLECTION]
    or_terms: list[dict] = []
    if employee_id_str:
        or_terms.append({"payload.employeeId": employee_id_str})
    if employee_number:
        or_terms.append({"payload.employeeNumber": employee_number})
        or_terms.append({"payload.employeeId": employee_number})
    if full_name:
        last_name = full_name.split(",")[0].strip().replace(" ", "")
        if len(last_name) >= 2:
            or_terms.append({"payload.employeeName": {"$regex": f"^{last_name[:4]}", "$options": "i"}})

    if or_terms:
        cursor = collection.find({"$or": or_terms}).sort("payload.updatedAt", -1).limit(1)
        docs = await cursor.to_list(length=1)
        if docs:
            try:
                return HRPayrollConfigRead(**docs[0]["payload"])
            except ValidationError as e:
                print(f"WARNING: Invalid synced HR payroll config: {e}")

    employee_collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    employee_doc = await employee_collection.find_one({"payload.employeeId": employee_number})
    if employee_doc:
        payload = employee_doc.get("payload", {})
        base_salary = payload.get("baseSalary", 0)
        if base_salary and float(base_salary) > 0:
            return HRPayrollConfigRead(
                id=payload.get("_id"),
                employeeId=payload.get("employeeId"),
                basicSalary=base_salary,
                housingAllowance=0.0,
                transportAllowance=0.0,
                mealAllowance=0.0,
                otherAllowances=0.0,
            )

    return None


# --- OVERTIME INTEGRATION ---
OVERTIME_REQUESTS_COLLECTION = "OvertimeRequests"

async def get_hr_overtime_requests(
    employee_id: str = None,
    start_date = None,
    end_date = None
):
    """
    Queries raw overtime requests from the HR System database.
    Enriches with Employee Name for our approval UI.
    """
    from core.database import hr_db
    collection = hr_db[OVERTIME_REQUESTS_COLLECTION]
    query = {}
    
    if employee_id:
        query["employeeId"] = employee_id

    if start_date and end_date:
        query["date"] = {"$gte": start_date, "$lte": end_date}

    cursor = collection.find(query).sort("date", -1).limit(200)
    docs = await cursor.to_list(length=200)

    enriched = []
    # Import here to avoid circular
    from integrations.hr.adapter import EMPLOYEES_COLLECTION
    
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        eid = doc.get("employeeId")
        
        if eid:
            emp = await hr_db[EMPLOYEES_COLLECTION].find_one({"employeeId": str(eid).strip()})
            if emp:
                doc["fullName"] = f"{emp.get('lastName')}, {emp.get('firstName')}"
            else:
                doc["fullName"] = f"Unknown ({eid})"
        
        enriched.append(doc)
        
    return enriched


async def get_synced_attendance_list(
    employee_number: Optional[str],
    start_date: datetime,
    end_date: datetime,
) -> List[dict]:
    collection = db[SYNCED_HR_ATTENDANCE_COLLECTION]
    query = {}
    if employee_number:
        query["employee_number"] = employee_number

    cursor = collection.find(query)
    docs = await cursor.to_list(length=None)

    employee_numbers = {
        str(doc.get("employee_number") or doc.get("payload", {}).get("employeeId") or "").strip()
        for doc in docs
    }
    name_map = await _get_synced_employee_name_map(employee_numbers)

    records = []
    for doc in docs:
        payload = doc.get("payload", {})
        payload["_id"] = str(payload.get("_id", doc.get("source_id")))
        parsed_date = _parse_hr_datetime(payload.get("date"))
        if not parsed_date:
            continue
        if start_date <= parsed_date <= end_date:
            employee_no = str(payload.get("employeeId", "")).strip()
            if employee_no and "employeeName" not in payload:
                payload["employeeName"] = name_map.get(employee_no, f"Unknown ({employee_no})")
            records.append(payload)

    records.sort(key=lambda item: item.get("date") or "", reverse=True)
    return records


async def get_synced_leave_list(
    employee_number: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    approved_only: bool = False,
) -> List[dict]:
    collection = db[SYNCED_HR_LEAVES_COLLECTION]
    query = {}
    if employee_number:
        query["employee_number"] = employee_number
    if approved_only:
        query["status"] = {"$regex": "^approved$", "$options": "i"}

    docs = await collection.find(query).to_list(length=None)
    employee_numbers = {
        str(doc.get("employee_number") or doc.get("payload", {}).get("employeeId") or "").strip()
        for doc in docs
    }
    name_map = await _get_synced_employee_name_map(employee_numbers)
    results = []
    for doc in docs:
        payload = doc.get("payload", {})
        payload["_id"] = str(payload.get("_id", doc.get("source_id")))

        start_dt = _parse_hr_datetime(payload.get("startDate"))
        end_dt = _parse_hr_datetime(payload.get("endDate"))
        if start_date and end_date:
            if not start_dt or not end_dt:
                continue
            if end_dt < start_date or start_dt > end_date:
                continue

        employee_no = str(payload.get("employeeId") or payload.get("employeeNumber") or "").strip()
        if employee_no and "fullName" not in payload:
            payload["fullName"] = name_map.get(employee_no, f"Unknown ({employee_no})")
        results.append(payload)

    results.sort(key=lambda item: item.get("startDate") or "", reverse=True)
    return results


async def get_synced_approved_leave_dates(
    employee_number: str,
    start_date: datetime,
    end_date: datetime,
) -> set[date]:
    collection = db[SYNCED_HR_LEAVES_COLLECTION]
    cursor = collection.find({
        "employee_number": employee_number,
        "status": {"$regex": "^approved$", "$options": "i"},
    })
    docs = await cursor.to_list(length=None)

    leave_dates: set[date] = set()
    for doc in docs:
        payload = doc.get("payload", {})
        start_dt = _parse_hr_datetime(payload.get("startDate"))
        end_dt = _parse_hr_datetime(payload.get("endDate"))
        if not start_dt or not end_dt:
            continue

        for leave_day in _iter_overlapping_dates(start_dt, end_dt, start_date, end_date):
            leave_dates.add(leave_day)

    return leave_dates


async def get_synced_overtime_requests(
    employee_number: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[dict]:
    collection = db[SYNCED_HR_OVERTIME_REQUESTS_COLLECTION]
    query = {}
    if employee_number:
        query["employee_number"] = employee_number

    docs = await collection.find(query).to_list(length=None)
    employee_numbers = {
        str(doc.get("employee_number") or doc.get("payload", {}).get("employeeId") or "").strip()
        for doc in docs
    }
    name_map = await _get_synced_employee_name_map(employee_numbers)
    results = []
    for doc in docs:
        payload = doc.get("payload", {})
        payload["_id"] = str(payload.get("_id", doc.get("source_id")))

        parsed_date = _parse_hr_datetime(payload.get("date"))
        if start_date and end_date:
            if not parsed_date or parsed_date < start_date or parsed_date > end_date:
                continue

        employee_no = str(payload.get("employeeId") or payload.get("employeeNumber") or "").strip()
        if employee_no and "fullName" not in payload:
            payload["fullName"] = name_map.get(employee_no, f"Unknown ({employee_no})")
        results.append(payload)

    results.sort(key=lambda item: item.get("date") or "", reverse=True)
    return results
