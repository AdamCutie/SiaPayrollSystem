import asyncio
import sys
import json
from pathlib import Path
from bson import json_util

# Setup project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import hr_db, check_db_connection

async def debug_hr_link():
    await check_db_connection()
    
    print("--- 1. Checking Employees Collection ---")
    emp_coll = hr_db["Employees"]
    emp = await emp_coll.find_one({"isActive": True})
    if emp:
        print(f"Sample Employee found: {emp.get('lastName')}, {emp.get('firstName')}")
        print(f"Employee _id: {emp.get('_id')} (type: {type(emp.get('_id'))})")
        print(f"Employee employeeId: {emp.get('employeeId')} (type: {type(emp.get('employeeId'))})")
    else:
        print("No active employees found.")
        return

    print("\n--- 2. Checking PayrollConfigurations Collection ---")
    config_coll = hr_db["PayrollConfigurations"]
    config = await config_coll.find_one({})
    if config:
        print(f"Sample Salary Doc found.")
        # Print all keys to see what fields they use for linking
        print(f"Available keys in Salary doc: {list(config.keys())}")
        print(f"Salary employeeId: {config.get('employeeId')} (type: {type(config.get('employeeId'))})")
        
        # Try to find a match manually
        match = await config_coll.find_one({"employeeNumber": emp.get('employeeId')})
        print(f"Search by human number '{emp.get('employeeId')}' in 'employeeNumber' field: {'FOUND' if match else 'NOT FOUND'}")
        
        match_id = await config_coll.find_one({"employeeId": emp.get('_id')})
        print(f"Search by database _id '{emp.get('_id')}': {'FOUND' if match_id else 'NOT FOUND'}")
    else:
        print("PayrollConfigurations collection is empty!")

    print("\n--- 4. Checking first 5 Salaries in DB ---")
    async for sal in config_coll.find({}).limit(5):
        sal_name = sal.get("employeeName")
        sal_num = sal.get("employeeNumber")
        sal_eid = sal.get("employeeId")
        print(f"Salary for: {sal_name} (Number: {sal_num}, empId: {sal_eid})")
        
        # Try to find this person in Employees
        e_match = await emp_coll.find_one({"lastName": {"$regex": sal_name.split(",")[0] if sal_name else "", "$options": "i"}})
        if e_match:
            print(f"  MATCH FOUND in Employees: {e_match.get('lastName')}, {e_match.get('firstName')} (ID: {e_match.get('employeeId')})")
        else:
            print(f"  NO MATCH in Employees for name '{sal_name}'")

if __name__ == "__main__":
    asyncio.run(debug_hr_link())
