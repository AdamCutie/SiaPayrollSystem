import asyncio
import sys
from pathlib import Path

# Setup project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import hr_db, check_db_connection

async def investigate_attendance_link():
    await check_db_connection()
    
    print("--- 1. Getting sample employee ---")
    emp = await hr_db["Employees"].find_one({"isActive": True})
    if not emp:
        print("No active employees found.")
        return
    
    eid_val = emp.get("employeeId")
    ename = f"{emp.get('lastName')}, {emp.get('firstName')}"
    print(f"Employee: {ename}")
    print(f"Employee Number (employeeId field): {eid_val}")

    print("\n--- 2. Searching for this employee in Attendance ---")
    # Search by employeeId exactly
    match = await hr_db["Attendance"].find_one({"employeeId": eid_val})
    if match:
        print(f"SUCCESS: Found attendance record using '{eid_val}'")
        print(f"Attendance Doc Sample: {match}")
    else:
        print(f"FAILED: No attendance record found using '{eid_val}'")
        
        # Search by name instead to see what ID they use
        match_by_name = await hr_db["Attendance"].find_one({"employeeName": ename})
        if match_by_name:
            print(f"FOUND by name! Let's see the ID they use...")
            print(f"Attendance employeeId field: {match_by_name.get('employeeId')}")
            print(f"Attendance employeeName field: {match_by_name.get('employeeName')}")
        else:
            print("Also FAILED to find by name.")

if __name__ == "__main__":
    asyncio.run(investigate_attendance_link())
