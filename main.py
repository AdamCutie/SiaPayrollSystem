from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.database import check_db_connection

# Import our New Processing Router
from modules.processing.router import router as processing_router

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
        # We don't crash, but we warn the developer
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

# Register our Modules
# Prefixing with '/payroll' groups all payroll-related logic together.
# This tells FastAPI: "Any URL starting with /payroll should use the processing_router."
app.include_router(processing_router, prefix="/payroll")

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
