import os
import json
import pytest
import httpx
import html
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_clozemaster_forecast_structure():
    """
    Diagnostic test to see the real structure of 'more-stats' response.
    The current Rust implementation assumes:
    reviewForecast: [ { "count": N }, ... ]
    """
    email = os.getenv("CLOZEMASTER_EMAIL")
    password = os.getenv("CLOZEMASTER_PASSWORD")
    
    if not email or not password:
        pytest.skip("CLOZEMASTER credentials not set")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Login
        login_url = "https://www.clozemaster.com/login"
        resp = await client.get(login_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'authenticity_token'})['value']
        
        await client.post(login_url, data={
            "user[login]": email,
            "user[password]": password,
            "authenticity_token": csrf_token,
            "commit": "Log In"
        })
        
        # 2. Get Dashboard for LP IDs and fresh CSRF
        resp = await client.get("https://www.clozemaster.com/dashboard")
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Extract CSRF from meta
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        if csrf_meta:
            dashboard_csrf = csrf_meta['content']
        else:
            dashboard_csrf = csrf_token

        dashboard_div = soup.find('div', {'data-react-class': 'DashboardV5'})
        props = json.loads(html.unescape(dashboard_div['data-react-props']))
        
        # Find Arabic or Greek
        pair = None
        for p in props.get("languagePairings", []):
            if p.get("slug") in ["ara-eng", "ell-eng"]:
                pair = p
                break
        
        if not pair:
            pytest.skip("No Arabic or Greek pairing found")
            
        lp_id = pair['id']
        lang_slug = pair['slug']
        
        # 3. Call more-stats
        api_url = f"https://www.clozemaster.com/api/v1/lp/{lp_id}/more-stats"
        headers = {
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.clozemaster.com/l/{lang_slug}",
            "X-CSRF-Token": dashboard_csrf
        }
        
        resp = await client.get(api_url, headers=headers)
        assert resp.status_code == 200
        
        data = resp.json()
        print(f"\nAPI Response Keys: {list(data.keys())}")
        
        forecast = data.get("reviewForecast", [])
        print(f"Forecast type: {type(forecast)}")
        if forecast:
            print(f"First element: {forecast[0]} (Type: {type(forecast[0])})")
            
            # THE BUG: In Python script it handles both Dict and raw values:
            # tomorrow_data.get("count", 0) if isinstance(tomorrow_data, dict) else tomorrow_data
            
            if isinstance(forecast[0], dict):
                assert "count" in forecast[0], "Dict element missing 'count' key"
            else:
                print("Elements are RAW values, not dicts!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_clozemaster_forecast_structure())
