import asyncio
import sys
from pathlib import Path

# Setup project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import hr_db, check_db_connection

async def check_2026_salaries():
    await check_db_connection()
    config_coll = hr_db["PayrollConfigurations"]
    
    # Check by employeeNumber
    count_num = await config_coll.count_documents({"employeeNumber": {"$regex": "^26-"}})
    print(f"Salaries with employeeNumber starting with '26-': {count_num}")
    
    # Check by employeeName just in case
    count_name = await config_coll.count_documents({"employeeName": {"$regex": "26-"}})
    print(f"Salaries with '26-' in employeeName: {count_name}")

    if count_num == 0:
        print("\nCONCLUSION: The HR System's Salary table contains NO records for the year 2026 employees.")

if __name__ == "__main__":
    asyncio.run(check_2026_salaries())
