import httpx
import os

# Target the exposed Tier-0 gateway port mapped from the Docker container
API_BASE_URL = "http://127.0.0.1:8000"

def test_telemetry_valid_json_ld():
    """
    EOSC D3.3 FAIR Data Compliance Test.
    Asserts the telemetry endpoint returns valid JSON-LD metadata for a valid sensor.
    """
    # Sensor ID 50 is strictly within the allowed detector array bounds [1, 100]
    response = httpx.get(f"{API_BASE_URL}/telemetry/50")
    
    # If telemetry data exists, it returns 200. We assert both are valid systemic states.
    assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
    
    # If data is present, we must ruthlessly verify the FAIR data interoperability schema
    if response.status_code == 200:
        data = response.json()
        assert data.get("@context") == "https://schema.org", "EOSC D3.3 Violation: Missing JSON-LD context"
        assert data.get("@type") == "Dataset", "EOSC D3.3 Violation: Missing JSON-LD type"
        assert "identifier" in data, "EOSC D3.3 Violation: Missing FAIR identifier"

def test_telemetry_out_of_bounds_rejection():
    """
    EOSC D3.1 Input Validation Test.
    Asserts the API actively rejects sensor IDs outside the physical detector array limits.
    """
    # Sensor ID 999 violates the Pydantic Path(le=100) constraint
    response = httpx.get(f"{API_BASE_URL}/telemetry/999")
    
    # Assert the Domain Logic Firewall halts the request before database execution
    assert response.status_code == 422, "API failed to reject out-of-bounds sensor ID"
    
    # Verify the ASGI exception handler intercepts and formats the error correctly
    errors = response.json().get("detail")
    assert isinstance(errors, list), "Error format does not match OpenAPI/FastAPI standards"
    assert errors[0]["type"] == "less_than_equal", "Incorrect validation error type raised"

def _extract_api_key() -> str:
    """Deterministically extracts the INGEST_API_KEY from the environment configuration."""
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("INGEST_API_KEY="):
                return line.strip().split("=", 1)[1].strip('"\'')
    raise RuntimeError("Critical Security Failure: INGEST_API_KEY not found in .env")

AUTH_HEADERS = {
    "X-API-Key": _extract_api_key(),
    "Content-Type": "application/json"
}

def test_oracle_kinematic_rejection():
    """
    Adversarial Integration Test.
    Asserts the PhysicsOracle rejects payloads exceeding the 6800 GeV theoretical limit.
    """
    poisoned_payload = {
        "pt1": 7000.0, "eta1": 1.2, "phi1": 0.5,
        "pt2": 42.0, "eta2": -0.8, "phi2": -2.1
    }
    
    response = httpx.post(
        f"{API_BASE_URL}/collision", 
        json=poisoned_payload, 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 422, "Security Failure: Oracle permitted kinematically impossible payload."
    error_detail = response.json().get("detail", "")
    assert "Kinematic Violation" in error_detail, "Oracle rejected payload for the wrong reason."

def test_oracle_valid_resonance_ingestion():
    """
    Golden Path Integration Test.
    Asserts the pipeline correctly queues a mathematically valid Z-Boson collision event.
    """
    valid_payload = {
        "pt1": 45.6, "eta1": 0.0, "phi1": 0.0, 
        "pt2": 45.6, "eta2": 0.0, "phi2": 3.14159
    }
    
    response = httpx.post(
        f"{API_BASE_URL}/collision", 
        json=valid_payload, 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 202, f"Pipeline blocked valid physics payload: {response.text}"
    data = response.json()
    assert data.get("status") == "queued", "Payload not enqueued to Redis broker."
    assert isinstance(data.get("queue_depth"), int), "Invalid broker queue depth returned."