from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

# Initialize the Motor Client for Async MongoDB operations
# The client manages a pool of connections automatically.
client = AsyncIOMotorClient(settings.MONGODB_URL)

# Reference to the Payroll System's internal database (for writes/reads)
db = client[settings.DATABASE_NAME]

# Reference to the existing HR System's database (for read-only integration)
hr_db = client[settings.HR_DATABASE_NAME]

async def check_db_connection():
    """
    Utility to verify that the MongoDB server is reachable.
    Used during application startup in main.py.
    """
    try:
        # The ping command is a lightweight way to check connectivity
        await client.admin.command('ping')
        return True
    except Exception as e:
        # Log the error if the connection fails
        print(f"CRITICAL: Could not connect to MongoDB at {settings.MONGODB_URL}: {e}")
        return False
