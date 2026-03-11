from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.database import check_db_connection

# --- Import Module Routers ---
from modules.processing.router import router as processing_router
from modules.dashboard.router import router as dashboard_router
from modules.employees.router import router as employee_router
from modules.attendance.router import router as attendance_router
from modules.leaves.router import router as leave_router
from modules.holidays.router import router as holiday_router
from modules.departments.router import router as department_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Manager.
    Handles operations that need to run when the server starts and stops.
    """
    # --- Startup Logic ---
    print("--- Starting SiaPayrollSystem ---")
    db_connected = await check_db_connection()
    
    if db_connected:
        print("✅ MongoDB Connection: SUCCESS.")
    else:
        print("❌ MongoDB Connection: FAILED. Check your .env configuration.")
    
    yield  # The application is now serving requests
    
    # --- Shutdown Logic ---
    print("--- Shutting down SiaPayrollSystem ---")

# Initialize the FastAPI Application
app = FastAPI(
    title="SiaPayrollSystem",
    description="A modern FastAPI standalone Payroll system integrating with legacy HR.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Register Module Routers ---
# Dashboard Overview (Admin Page)
app.include_router(dashboard_router, prefix="/payroll")

# Payroll Processing (Calculations and Snapshots)
app.include_router(processing_router, prefix="/payroll")

# Employee Management (Profile and List)
app.include_router(employee_router, prefix="/payroll")

# Attendance and Work Logs (Dashboard Table)
app.include_router(attendance_router, prefix="/payroll")

# Leaves and Holidays
app.include_router(leave_router, prefix="/payroll")
app.include_router(holiday_router, prefix="/payroll")

# Departments (Horizontal Cards)
app.include_router(department_router, prefix="/payroll")

@app.get("/", tags=["Health"])
async def health_check():
    """
    Basic health check endpoint to verify the API is online.
    """
    return {
        "status": "Online",
        "system": "SiaPayrollSystem",
        "message": "API is operational",
        "documentation": "/docs"
    }
