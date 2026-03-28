import asyncio
import sys
from pathlib import Path

# Setup project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import hr_db, check_db_connection

async def count_types():
    await check_db_connection()
    coll = hr_db["Employees"]
    
    pipeline = [
        {"$match": {"isActive": True}},
        {"$group": {"_id": "$contractType", "count": {"$sum": 1}}}
    ]
    
    results = await coll.aggregate(pipeline).to_list(None)
    
    print("--- HR DATABASE REALITY (Active Employees) ---")
    for r in results:
        label = r.get("_id") or "EMPTY/NULL"
        count = r.get("count")
        print(f"{label}: {count} employees")

if __name__ == "__main__":
    asyncio.run(count_types())
