from motor.motor_asyncio import AsyncIOMotorCollection
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from core.database import db, hr_db
from pydantic import ValidationError
from .schemas import HREmployeeRead, HRPayrollConfigRead, HRPayrollConfigUpdate, HRRoleSalaryRead
from bson import ObjectId
from modules.agencies.service import AgencyCalculator

# 1. Define the Collection Names as they exist in the legacy DB
EMPLOYEES_COLLECTION = "Employees"
ROLE_SALARIES_COLLECTION = "RoleSalaries"
ATTENDANCE_COLLECTION = "Attendance"
LEAVES_COLLECTION = "Leaves"

# Optional fallback config storage inside the payroll DB (keeps HR DB read-only)
SYNCED_HR_EMPLOYEES_COLLECTION = "SyncedHREmployees"
SYNCED_HR_ROLE_SALARIES_COLLECTION = "SyncedHRRoleSalaries"
SYNCED_HR_ATTENDANCE_COLLECTION = "SyncedHRAttendance"
SYNCED_HR_LEAVES_COLLECTION = "SyncedHRLeaves"
SYNCED_HR_OVERTIME_REQUESTS_COLLECTION = "SyncedHROvertimeRequests"
SYNCED_HR_UNDERTIME_RECORDS_COLLECTION = "SyncedHRUndertimeRecords"

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
            emp = await db[SYNCED_HR_EMPLOYEES_COLLECTION].find_one({"payload.employeeId": eid})
            if emp:
                payload = emp.get("payload", {})
                emp_cache[eid] = f"{payload.get('lastName')}, {payload.get('firstName')}"
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
            
            # Search by the human employee number in the SYNCED collection
            emp = await db[SYNCED_HR_EMPLOYEES_COLLECTION].find_one({"payload.employeeId": clean_eid})
            if emp:
                payload = emp.get("payload", {})
                emp_cache[eid] = f"{payload.get('lastName')}, {payload.get('firstName')}"
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

async def get_all_active_employees(limit: int | None = None) -> List[HREmployeeRead]:
    """
    Fetches all active employees from our synced local database.
    """
    collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    cursor = collection.find({"payload.isActive": True})
    if limit is not None:
        cursor = cursor.limit(limit)

    employees: List[HREmployeeRead] = []
    async for doc in cursor:
        try:
            employees.append(HREmployeeRead(**doc.get("payload", {})))
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


async def _get_synced_employee_info_map(employee_numbers: set[str]) -> dict[str, dict]:
    if not employee_numbers:
        return {}

    collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    docs = await collection.find({"payload.employeeId": {"$in": list(employee_numbers)}}).to_list(length=None)

    info: dict[str, dict] = {}
    for doc in docs:
        payload = doc.get("payload", {})
        employee_number = str(payload.get("employeeId", "")).strip()
        if not employee_number:
            continue
        first_name = payload.get("firstName", "")
        last_name = payload.get("lastName", "")
        info[employee_number] = {
            "name": f"{last_name}, {first_name}".strip(", "),
            "department": payload.get("department", "N/A"),
            "role": payload.get("role", "N/A")
        }

    return info


async def get_employee_by_email(email: str) -> Optional[HREmployeeRead]:
    """
    Fetches a single employee record from our synced local database by email.
    """
    collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    doc = await collection.find_one({"payload.email": email})
    if not doc:
        return None

    try:
        return HREmployeeRead(**doc.get("payload", {}))
    except ValidationError as e:
        doc_id = doc.get("_id", "<unknown>")
        print(f"WARNING: Synced HR employee record invalid for _id={doc_id}: {e}")
        return None


async def get_employee_by_id(employee_id_str: str) -> Optional[HREmployeeRead]:
    """
    Fetches a single employee record from our synced local database by MongoDB _id or employeeId.
    """
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

async def get_employee_payroll_config(
    employee_id_str: str,
    employee_number: str,
    full_name: str
) -> Optional[HRPayrollConfigRead]:
    """
    Fetches the LATEST salary settings for an employee.
    PRIORITY:
    1. Role-Based Salaries (SyncedHRRoleSalaries - Primary Source)
    2. Fallback: 'baseSalary' directly from Employees table
    """
    
    # Prerequisite: Fetch the basic employee record to determine their role
    emp_record = await get_employee_by_id(employee_id_str)
    if not emp_record and employee_number:
        # Fallback to fetching by employee number if ID failed
        emp_record = await get_employee_by_id(employee_number)

    # --- 1. PRIORITY 1: ROLE-BASED SALARIES (SYNCED) ---
    if emp_record and emp_record.role:
        role_salary_doc = await db[SYNCED_HR_ROLE_SALARIES_COLLECTION].find_one({
            "payload.roleName": emp_record.role,
            "payload.isActive": True
        })
        if role_salary_doc:
            try:
                rs = HRRoleSalaryRead(**role_salary_doc["payload"])
                salary = float(rs.baseSalary)
                daily_rate = round(salary / 26.0, 2)
                hourly_rate = round(daily_rate / 8.0, 2)

                # We wrap the role salary into the payroll config schema
                return HRPayrollConfigRead(
                    id=str(rs.id),
                    employeeId=emp_record.employeeId,
                    basicSalary=salary,
                    housingAllowance=0.0,
                    transportAllowance=0.0,
                    mealAllowance=0.0,
                    otherAllowances=0.0,
                    absencePenaltyRate=daily_rate,
                    latePenaltyRate=hourly_rate,
                    withholdingTax=_calculate_estimated_withholding_tax(salary)
                )
            except ValidationError as e:
                print(f"WARNING: Invalid role salary doc for role {emp_record.role}: {e}")

    # --- 2. FALLBACK: USE 'baseSalary' FROM EMPLOYEES TABLE ---
    if emp_record and emp_record.baseSalary > 0:
        salary = float(emp_record.baseSalary)
        daily_rate = round(salary / 26.0, 2)
        hourly_rate = round(daily_rate / 8.0, 2)

        return HRPayrollConfigRead(
            id=emp_record.id,
            employeeId=emp_record.employeeId,
            basicSalary=salary,
            housingAllowance=0.0,
            transportAllowance=0.0,
            mealAllowance=0.0,
            otherAllowances=0.0,
            absencePenaltyRate=daily_rate,
            latePenaltyRate=hourly_rate,
            withholdingTax=_calculate_estimated_withholding_tax(salary)
        )

    return None


async def get_synced_employee_payroll_config(
    employee_id_str: str,
    employee_number: str,
    full_name: str
) -> Optional[HRPayrollConfigRead]:
    """
    Fetches salary settings from the local SYNCED database.
    Used for UI previews and speed.
    """
    
    # 1. Try Role-Based Salaries first (Our new standard)
    employee_collection = db[SYNCED_HR_EMPLOYEES_COLLECTION]
    employee_doc = await employee_collection.find_one({"payload.employeeId": employee_number})
    
    if employee_doc:
        payload = employee_doc.get("payload", {})
        role = payload.get("role")
        if role:
            role_salary_doc = await db[SYNCED_HR_ROLE_SALARIES_COLLECTION].find_one({
                "payload.roleName": role,
                "payload.isActive": True
            })
            if role_salary_doc:
                try:
                    rs = HRRoleSalaryRead(**role_salary_doc["payload"])
                    salary = float(rs.baseSalary)
                    daily_rate = round(salary / 26.0, 2)
                    hourly_rate = round(daily_rate / 8.0, 2)

                    return HRPayrollConfigRead(
                        id=str(rs.id),
                        employeeId=payload.get("employeeId"),
                        basicSalary=salary,
                        housingAllowance=0.0,
                        transportAllowance=0.0,
                        mealAllowance=0.0,
                        otherAllowances=0.0,
                        absencePenaltyRate=daily_rate,
                        latePenaltyRate=hourly_rate,
                        withholdingTax=_calculate_estimated_withholding_tax(salary)
                    )
                except ValidationError as e:
                    print(f"WARNING: Invalid role salary doc for role {role}: {e}")

    # 2. Fallback to Employee baseSalary field
    if employee_doc:
        payload = employee_doc.get("payload", {})
        base_salary = payload.get("baseSalary", 0)
        if base_salary and float(base_salary) > 0:
            salary = float(base_salary)
            # Default penalty rates: Daily rate and Hourly rate
            daily_rate = round(salary / 26.0, 2)
            hourly_rate = round(daily_rate / 8.0, 2)

            return HRPayrollConfigRead(
                id=payload.get("_id"),
                employeeId=payload.get("employeeId"),
                basicSalary=salary,
                housingAllowance=0.0,
                transportAllowance=0.0,
                mealAllowance=0.0,
                otherAllowances=0.0,
                absencePenaltyRate=daily_rate,
                latePenaltyRate=hourly_rate,
                withholdingTax=_calculate_estimated_withholding_tax(salary)
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
            emp = await db[SYNCED_HR_EMPLOYEES_COLLECTION].find_one({"payload.employeeId": str(eid).strip()})
            if emp:
                payload = emp.get("payload", {})
                doc["fullName"] = f"{payload.get('lastName')}, {payload.get('firstName')}"
            else:
                doc["fullName"] = f"Unknown ({eid})"
        
        enriched.append(doc)
        
    return enriched


async def get_synced_attendance_list(
    employee_number: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> List[dict]:
    collection = db[SYNCED_HR_ATTENDANCE_COLLECTION]
    query = {}
    if employee_number:
        query["employee_number"] = employee_number

    # 🚀 OPTIMIZATION: Push date filtering to MongoDB level
    if start_date and end_date:
        query["payload.date"] = {
            "$gte": start_date.isoformat() if isinstance(start_date, datetime) else start_date,
            "$lte": end_date.isoformat() if isinstance(end_date, datetime) else end_date
        }

    cursor = collection.find(query)
    docs = await cursor.to_list(length=None)

    employee_numbers = {
        str(doc.get("employee_number") or doc.get("payload", {}).get("employeeId") or "").strip()
        for doc in docs
    }
    info_map = await _get_synced_employee_info_map(employee_numbers)

    records = []
    for doc in docs:
        payload = doc.get("payload", {})
        payload["_id"] = str(payload.get("_id", doc.get("source_id")))
        parsed_date = _parse_hr_datetime(payload.get("date"))
        if not parsed_date:
            continue
            
        # Ensure parsed_date is offset-aware for comparison if start_date is
        if parsed_date.tzinfo is None and start_date and start_date.tzinfo is not None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            
        # Keep Python-side filter as a fallback for non-standard formats
        if start_date and end_date:
            if not (start_date <= parsed_date <= end_date):
                continue
                
        employee_no = str(payload.get("employeeId", "")).strip()
        if employee_no:
            info = info_map.get(employee_no)
            if info:
                # If name is generic or missing, use info map
                if not payload.get("employeeName") or "Unknown" in payload.get("employeeName", ""):
                    payload["employeeName"] = info["name"]
                
                # ALWAYS overwrite "all" or "N/A" or missing department/role with the specific one from employee mirror
                current_dept = str(payload.get("department", "")).lower()
                if not payload.get("department") or current_dept in ["all", "n/a", "none"]:
                    payload["department"] = info["department"]
                
                current_role = str(payload.get("role", "")).lower()
                if not payload.get("role") or current_role in ["all", "n/a", "none"]:
                    payload["role"] = info["role"]
            else:
                if "employeeName" not in payload:
                    payload["employeeName"] = f"Unknown ({employee_no})"

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

    # 🚀 OPTIMIZATION: Push date filtering to MongoDB level
    if start_date and end_date:
        s_str = start_date.isoformat() if isinstance(start_date, datetime) else start_date
        e_str = end_date.isoformat() if isinstance(end_date, datetime) else end_date
        # Query where the leave period overlaps with our search range
        query["$or"] = [
            {"payload.startDate": {"$gte": s_str, "$lte": e_str}},
            {"payload.endDate": {"$gte": s_str, "$lte": e_str}}
        ]

    docs = await collection.find(query).to_list(length=None)
    employee_numbers = {
        str(doc.get("employee_number") or doc.get("payload", {}).get("employeeId") or "").strip()
        for doc in docs
    }
    info_map = await _get_synced_employee_info_map(employee_numbers)
    results = []
    for doc in docs:
        payload = doc.get("payload", {})
        payload["_id"] = str(payload.get("_id", doc.get("source_id")))

        start_dt = _parse_hr_datetime(payload.get("startDate"))
        end_dt = _parse_hr_datetime(payload.get("endDate"))
        
        # Keep Python-side filter as a fallback for non-standard formats
        if start_date and end_date:
            if not start_dt or not end_dt:
                continue
            if end_dt < start_date or start_dt > end_date:
                continue

        employee_no = str(payload.get("employeeId") or payload.get("employeeNumber") or "").strip()
        if employee_no:
            info = info_map.get(employee_no)
            if info:
                if "fullName" not in payload:
                    payload["fullName"] = info["name"]
                if "department" not in payload:
                    payload["department"] = info["department"]
            else:
                if "fullName" not in payload:
                    payload["fullName"] = f"Unknown ({employee_no})"

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

    # 🚀 OPTIMIZATION: Push date filtering to MongoDB level
    if start_date and end_date:
        query["payload.date"] = {
            "$gte": start_date.isoformat() if isinstance(start_date, datetime) else start_date,
            "$lte": end_date.isoformat() if isinstance(end_date, datetime) else end_date
        }

    docs = await collection.find(query).to_list(length=None)
    employee_numbers = {
        str(doc.get("employee_number") or doc.get("payload", {}).get("employeeId") or "").strip()
        for doc in docs
    }
    info_map = await _get_synced_employee_info_map(employee_numbers)
    results = []
    for doc in docs:
        payload = doc.get("payload", {})
        payload["_id"] = str(payload.get("_id", doc.get("source_id")))

        parsed_date = _parse_hr_datetime(payload.get("date"))
        
        # Keep Python-side filter as a fallback for non-standard formats
        if start_date and end_date:
            if not parsed_date or parsed_date < start_date or parsed_date > end_date:
                continue

        employee_no = str(payload.get("employeeId") or payload.get("employeeNumber") or "").strip()
        if employee_no:
            info = info_map.get(employee_no)
            if info:
                if "fullName" not in payload:
                    payload["fullName"] = info["name"]
                if "department" not in payload:
                    payload["department"] = info["department"]
            else:
                if "fullName" not in payload:
                    payload["fullName"] = f"Unknown ({employee_no})"

        results.append(payload)

    results.sort(key=lambda item: item.get("date") or "", reverse=True)
    return results

def _calculate_estimated_withholding_tax(basic_salary: float) -> float:
    """
    Helper to calculate a semi-monthly withholding tax estimate.
    Assumes standard statutory deductions (SSS, PHIC, HDMF) applied to basic salary.
    """
    if not basic_salary or basic_salary <= 0:
        return 0.0
        
    # 1. Semi-monthly basic pay (Gross estimate)
    gross_semi = basic_salary / 2.0
    
    # 2. Estimate Statutories (These are typically full amounts in 1st half)
    # For a conservative profile preview, we use the 1st half logic
    sss = AgencyCalculator.calculate_sss(basic_salary)
    phic = AgencyCalculator.calculate_philhealth(basic_salary)
    hdmf = AgencyCalculator.calculate_pagibig(basic_salary)
    
    # 3. Taxable Income
    taxable = max(0.0, gross_semi - (sss + phic + hdmf))
    
    # 4. Calculate Tax
    return AgencyCalculator.calculate_withholding_tax(taxable)


async def get_synced_undertime_records(
    employee_number: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[dict]:
    collection = db[SYNCED_HR_UNDERTIME_RECORDS_COLLECTION]
    query = {}
    if employee_number:
        query["employee_number"] = employee_number

    # 🚀 OPTIMIZATION: Push date filtering to MongoDB level
    if start_date and end_date:
        query["payload.date"] = {
            "$gte": start_date.isoformat() if isinstance(start_date, datetime) else start_date,
            "$lte": end_date.isoformat() if isinstance(end_date, datetime) else end_date
        }

    docs = await collection.find(query).to_list(length=None)
    employee_numbers = {
        str(doc.get("employee_number") or doc.get("payload", {}).get("employeeId") or "").strip()
        for doc in docs
    }
    info_map = await _get_synced_employee_info_map(employee_numbers)
    results = []
    for doc in docs:
        payload = doc.get("payload", {})
        payload["_id"] = str(payload.get("_id", doc.get("source_id")))

        parsed_date = _parse_hr_datetime(payload.get("date"))
        
        # Keep Python-side filter as a fallback for non-standard formats
        if start_date and end_date:
            if not parsed_date or parsed_date < start_date or parsed_date > end_date:
                continue

        employee_no = str(payload.get("employeeId") or payload.get("employeeNumber") or "").strip()
        if employee_no:
            info = info_map.get(employee_no)
            if info:
                if "fullName" not in payload:
                    payload["fullName"] = info["name"]
                if "department" not in payload:
                    payload["department"] = info["department"]
            else:
                if "fullName" not in payload:
                    payload["fullName"] = f"Unknown ({employee_no})"

        results.append(payload)

    results.sort(key=lambda item: item.get("date") or "", reverse=True)
    return results
