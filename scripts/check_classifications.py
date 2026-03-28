import asyncio
import sys
from pathlib import Path

# Setup project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import hr_db, check_db_connection

async def check_classifications():
    await check_db_connection()
    coll = hr_db["Employees"]
    types = await coll.distinct("contractType")
    print(f"--- UNIQUE HR CLASSIFICATIONS ---")
    print(types)

if __name__ == "__main__":
    asyncio.run(check_classifications())
