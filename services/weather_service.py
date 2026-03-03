import os
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("mecris")

class WeatherService:
    """Service to handle weather checks for Boris & Fiona walk reminders with caching."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.lat = os.getenv("LATITUDE", "41.6764")
        self.lon = os.getenv("LONGITUDE", "-86.2520")
        self.mock_mode = os.getenv("MOCK_WEATHER", "false").lower() == "true"
        
        # Cache implementation
        self._cache = {}
        self.cache_minutes = 60

    def get_weather(self) -> Dict[str, Any]:
        """Fetch current weather from OpenWeather with 1-hour cache or return mock data."""
        now = datetime.now()
        
        # Check cache
        if "data" in self._cache and "expires" in self._cache:
            if now < self._cache["expires"]:
                logger.debug("Returning cached weather data")
                return self._cache["data"]

        if self.mock_mode or not self.api_key:
            if not self.api_key and not self.mock_mode:
                logger.warning("OPENWEATHER_API_KEY not found, falling back to MOCK data")
            
            mock_data = {
                "temperature": 72.5,
                "description": "clear sky (mock)",
                "is_raining": False,
                "is_snowing": False,
                "wind_speed": 5.2,
                "sunrise": int(now.timestamp()) - 3600,
                "sunset": int(now.timestamp()) + 36000,
                "source": "mock"
            }
            # Cache the mock data too to avoid repeated logs
            self._update_cache(mock_data)
            return mock_data

        # OneCall 3.0 / Weather 2.5 endpoint
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={self.lat}&lon={self.lon}&appid={self.api_key}&units=imperial"
        
        try:
            logger.info(f"Fetching fresh weather data from OpenWeather (lat={self.lat}, lon={self.lon})")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            weather_main = [w["main"] for w in data.get("weather", [])]
            
            weather_data = {
                "temperature": data["main"]["temp"],
                "description": data["weather"][0]["description"] if data.get("weather") else "unknown",
                "is_raining": any(m in ["Rain", "Drizzle"] for m in weather_main),
                "is_snowing": "Snow" in weather_main,
                "wind_speed": data["wind"]["speed"],
                "sunrise": data["sys"]["sunrise"],
                "sunset": data["sys"]["sunset"],
                "source": "openweather"
            }
            
            self._update_cache(weather_data)
            return weather_data
            
        except Exception as e:
            logger.error(f"Weather API fetch failed: {e}")
            # If we have stale data, return it instead of an error to prevent breaking context
            if "data" in self._cache:
                logger.warning("Returning stale weather data due to API error")
                return {**self._cache["data"], "stale": True, "error": str(e)}
            
            return {"error": str(e), "source": "error"}

    def _update_cache(self, data: Dict[str, Any]):
        """Internal helper to update the local cache."""
        self._cache = {
            "data": data,
            "expires": datetime.now() + timedelta(minutes=self.cache_minutes)
        }

    def is_walk_appropriate(self, weather: Dict[str, Any]) -> Tuple[bool, str]:
        """Determine if current conditions are suitable for a walk."""
        if "error" in weather and "temperature" not in weather:
            return False, f"Weather data unavailable: {weather['error']}"

        temp = weather["temperature"]
        if temp < 20:
            return False, f"Too cold for the doggies ({temp}°F) ❄️"
        if temp > 95:
            return False, f"Too hot for a walk ({temp}°F) ☀️"
        
        if weather["is_raining"]:
            return False, "It's raining 🌧️"
        
        if weather["wind_speed"] > 30:
            return False, "Too windy! 💨"

        # Daylight logic
        now = int(datetime.now().timestamp())
        if now < weather["sunrise"]:
            return False, "Too early, sun isn't up yet 🌅"
        if now > weather["sunset"]:
            return False, "Too late, sun is down 🌑"

        return True, "Conditions are good for a walk! ✅"
