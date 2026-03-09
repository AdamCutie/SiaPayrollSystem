import pytest
from fastapi.testclient import TestClient
from main import app  # Import your FastAPI app

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

    # ACT:: Send the POST request to our new endpoint
    response = client.post("/payroll/processing/run", json=payload)

    # ASSERT: Check if the results are what we expect
    # we expect a 200 OK status code
    assert response.status_code == 200

    # We expect the JSON to have 'status' and 'processed_count'
    data = response.json()
    assert data["status"] == "success"
    assert "processed_count" in data["data"]

    print(f"\n Test Passed: {data['message']}")
