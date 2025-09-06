from playwright.sync_api import sync_playwright

def fetch_groq_usage():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://console.groq.com/usage")

        # Login flow (you may want to reuse cookies / tokens here)
        page.fill("input[name='email']", "your-email")
        page.fill("input[name='password']", "your-password")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # Extract usage values
        monthly_usage = page.inner_text("css=selector-for-monthly")
        daily_usage = page.inner_text("css=selector-for-daily")

        browser.close()
        return {
            "monthly_usage": monthly_usage,
            "daily_usage": daily_usage
        }
