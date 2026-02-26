from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.database import check_db_connection

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
        print("✅ Connected to MongoDB.")
    else:
        print("❌ FAILED to connect to MongoDB. The system may not function correctly.")
    
    yield  # The application is now serving requests
    
    # --- Shutdown Logic ---
    print("--- Shutting down SiaPayrollSystem ---")

# Initialize the FastAPI Application
app = FastAPI(
    title="SiaPayrollSystem",
    description="A standalone Payroll Monolith integrating with an existing HR system.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", tags=["Health"])
async def health_check():
    """
    Basic health check endpoint to verify the API is online.
    """
    return {
        "status": "Online",
        "message": "SiaPayrollSystem API is running",
        "docs": "/docs"
    }
