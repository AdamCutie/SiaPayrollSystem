import pytest
from fastapi.testclient import TestClient
from main import app  # Import your FastAPI app
from core.auth import require_admin
from modules.processing.service import PayrollProcessingService

# Initialize the TestClient
# This simulates a 'Fake' browser that can talk to your API
client = TestClient(app)


def test_run_payroll_api():
    """
    TEST: Verifies that the payroll run endpoint accepts
    dates
    and return a success message.
    """
    # Prepare the payload (The dates for the payroll period)
    payload = {
        "start_date": "2026-03-01T00:00:00",
        "end_date": "2026-03-15T23:59:59"
    }

    # Override admin auth dependency (unit-test style: we don't test JWT wiring here)
    app.dependency_overrides[require_admin] = lambda: object()

    # Mock payroll processing to avoid hitting a real MongoDB during tests
    async def _fake_run_full_payroll(cls, start_date, end_date):
        return 2

    original = PayrollProcessingService.run_full_payroll
    PayrollProcessingService.run_full_payroll = classmethod(_fake_run_full_payroll)

    try:
        # ACT: Send the POST request to our endpoint
        response = client.post("/payroll/processing/run", json=payload)
    finally:
        # Cleanup overrides/mocks for other tests
        app.dependency_overrides.clear()
        PayrollProcessingService.run_full_payroll = original

    # ASSERT: Check if the results are what we expect
    # we expect a 200 OK status code
    assert response.status_code == 200

    # We expect the JSON to have 'status' and 'processed_count'
    data = response.json()
    assert data["status"] == "success"
    assert data["processed_count"] == 2
