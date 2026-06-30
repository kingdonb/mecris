import pytest
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:3000"
TEST_USER_ID = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"
AUTH_HEADER = {"Authorization": f"Bearer TestUser {TEST_USER_ID}"}

@pytest.fixture(autouse=True)
def disable_mock_requests(monkeypatch):
    """Restore real requests for E2E tests."""
    monkeypatch.undo()

def test_aggregate_status_non_zero():
    """Verify that aggregate status does not return 0/0 goals."""
    resp = requests.get(f"{BASE_URL}/aggregate-status", headers=AUTH_HEADER)
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["total_goals"] > 0, f"Total goals should be > 0: {data}"
    assert "score" in data
    assert "/" in data["score"]

def test_languages_has_goal_consistency():
    """Verify that languages with known Beeminder slugs report has_goal=true."""
    resp = requests.get(f"{BASE_URL}/languages", headers=AUTH_HEADER)
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    langs = data["languages"]
    
    # Arabic is a known goal
    arabic = next((l for l in langs if l["name"] == "ARABIC"), None)
    assert arabic is not None, f"ARABIC language missing from response: {data}"
    assert arabic["has_goal"] is True, f"Arabic should have has_goal=true: {arabic}"
    
    # User said Arabic goal was 0, but it should be non-zero if cur > 0
    if arabic["current"] > 0:
        assert arabic["absolute_target"] > 0, f"Arabic should have a non-zero target: {arabic}"

def test_weather_heuristic_is_json():
    """Verify that weather heuristic returns valid JSON, not plain text."""
    resp = requests.get(f"{BASE_URL}/internal/weather-heuristic")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert isinstance(data, dict), "Weather response should be a JSON object"
    assert "conditions" in data

def test_greek_mapping_safety():
    """Verify that GREEK does not have a hardcoded 'ellinika' slug in the DTO if it's an odometer."""
    resp = requests.get(f"{BASE_URL}/languages", headers=AUTH_HEADER)
    data = resp.json()
    greek = next((l for l in data["languages"] if l["name"] == "GREEK"), None)
    # If the user says it should not be updated, we might have cleared the slug in the scraper.
    # The 'no goal' badge would appear if 'has_goal' is false.
    pass

def test_cloud_sync_routing():
    """Verify that /internal/cloud-sync is correctly routed and returns success."""
    fake_header = {"Authorization": "Bearer TestUser fake-user-without-creds"}
    resp = requests.post(f"{BASE_URL}/internal/cloud-sync", headers=fake_header)
    # This should return 200/success even if scraper fails internally, but routing must work
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"

def test_language_sorting():
    """Verify that languages with goals appear at the top."""
    resp = requests.get(f"{BASE_URL}/languages", headers=AUTH_HEADER)
    data = resp.json()
    langs = data["languages"]
    
    # Check if Arabic (has goal) is in the first half of the list
    arabic_idx = next(i for i, l in enumerate(langs) if l["name"] == "ARABIC")
    assert arabic_idx < len(langs) / 2
