from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure
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
        # Avoid printing credentials embedded in connection strings.
        print(f"CRITICAL: Could not connect to MongoDB. Check your .env MONGODB_URL. Details: {e}")
        return False


def close_db_connection() -> None:
    """
    Closes the underlying MongoDB client.
    Call this during application shutdown to release sockets cleanly.
    """
    client.close()


async def ensure_db_indexes() -> None:
    """
    Ensures critical MongoDB indexes exist for data correctness and safety.

    This is safe to call multiple times (idempotent).
    """
    try:
        await db["PayrollSnapshots"].create_index(
            [("employee_id", 1), ("pay_period_start", 1), ("pay_period_end", 1)],
            unique=True,
            name="uniq_employee_pay_period",
        )
        for collection_name in (
            "SyncedHREmployees",
            "SyncedHRPayrollConfigurations",
            "SyncedHRAttendance",
            "SyncedHRLeaves",
            "SyncedHROvertimeRequests",
        ):
            await db[collection_name].create_index(
                [("source_id", 1)],
                unique=True,
                name="uniq_source_id",
            )

        await db["HRSyncState"].create_index(
            [("scope", 1)],
            unique=True,
            name="uniq_scope",
        )
        await db["ActivityLogs"].create_index(
            [("timestamp", -1), ("module", 1)],
            name="idx_activity_logs_timestamp_module",
        )
        # Logical deduplication for Attendance: One record per employee per day
        await db["SyncedHRAttendance"].create_index(
            [("employee_number", 1), ("date", 1)],
            unique=True,
            name="uniq_attendance_logical_key",
        )
        # Logical deduplication for Undertime: One record per employee per day
        await db["SyncedHRUndertimeRecords"].create_index(
            [("employee_number", 1), ("date", 1)],
            unique=True,
            name="uniq_undertime_logical_key",
        )
    except OperationFailure as e:
        # Common cause: existing duplicate records prevent creating a unique index.
        print(f"WARNING: Could not create unique index on PayrollSnapshots: {e}")
    except Exception as e:
        print(f"WARNING: Could not ensure MongoDB indexes: {e}")
