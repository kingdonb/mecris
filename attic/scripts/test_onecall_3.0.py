import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_endpoints():
    api_key = os.getenv("OPENWEATHER_API_KEY")
    lat = os.getenv("LATITUDE", "41.6764")
    lon = os.getenv("LONGITUDE", "-86.2520")
    
    # 1. Current 2.5 endpoint
    url_25 = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=imperial"
    
    # 2. OneCall 3.0 endpoint (requires subscription)
    url_30 = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&appid={api_key}&units=imperial"

    print(f"Testing with API Key: {api_key[:5]}...{api_key[-5:]}")
    
    print("\n--- Testing 2.5 API ---")
    r25 = requests.get(url_25)
    print(f"Status: {r25.status_code}")
    if r25.status_code != 200:
        print(f"Response: {r25.text}")

    print("\n--- Testing OneCall 3.0 API ---")
    r30 = requests.get(url_30)
    print(f"Status: {r30.status_code}")
    if r30.status_code != 200:
        print(f"Response: {r30.text}")

if __name__ == "__main__":
    test_endpoints()
