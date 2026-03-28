import asyncio
import sys
from pathlib import Path

# Setup project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import hr_db, check_db_connection

async def check_employee_status():
    await check_db_connection()
    emp_coll = hr_db["Employees"]
    emp = await emp_coll.find_one({"isActive": True})
    if emp:
        print("--- SAMPLE EMPLOYEE DATA ---")
        for key, val in emp.items():
            print(f"{key}: {val} ({type(val)})")
    else:
        print("No active employees found.")

if __name__ == "__main__":
    asyncio.run(check_employee_status())
