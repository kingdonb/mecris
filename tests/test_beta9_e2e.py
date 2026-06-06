import pytest
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:3000"
TEST_USER_ID = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"
AUTH_HEADER = {"Authorization": f"Bearer TestUser {TEST_USER_ID}"}

def test_languages_dto_completeness():
    """Verify that /languages returns all fields required by the Android app."""
    resp = requests.get(f"{BASE_URL}/languages", headers=AUTH_HEADER)
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "languages" in data
    assert len(data["languages"]) > 0
    
    # Sort check: Arabic should be first or among first
    names = [l["name"] for l in data["languages"]]
    assert "ARABIC" in names
    
    lang = next(l for l in data["languages"] if l["name"] == "ARABIC")
    required_fields = [
        "name", "current", "tomorrow", "next_7_days", 
        "daily_rate", "safebuf", "derail_risk", 
        "pump_multiplier", "has_goal", "daily_completions",
        "absolute_target", "goal_met"
    ]
    for field in required_fields:
        assert field in lang, f"Missing field in ARABIC: {field}"
    
    assert lang["has_goal"] is True, "Arabic should have a goal associated"
    assert lang["absolute_target"] > 0, "Arabic target should be non-zero"

def test_aggregate_status_structure():
    """Verify /aggregate-status structure."""
    resp = requests.get(f"{BASE_URL}/aggregate-status", headers=AUTH_HEADER)
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "score" in data
    assert "goals_met" in data
    assert "total_goals" in data
    assert "components" in data
    assert "walk" in data["components"]
    assert "arabic" in data["components"]
    assert "greek" in data["components"]

def test_weather_heuristic_json():
    """Verify /internal/weather-heuristic returns JSON, not plain text."""
    resp = requests.get(f"{BASE_URL}/internal/weather-heuristic")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    # This will raise an error if not valid JSON
    data = resp.json()
    assert isinstance(data, dict)
    assert "conditions" in data
    assert "recommendation" in data
