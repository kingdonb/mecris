import asyncio
from unittest.mock import patch
import datetime
from dotenv import load_dotenv
from services.reminder_service import ReminderService
from mcp_server import get_narrator_context, get_coaching_insight

load_dotenv()

async def main():
    rs = ReminderService(get_narrator_context, get_coaching_insight)
    
    class MockDatetime(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 16, 15, 0, 0) # 3:00 PM on a day you presumably didn't walk

    with patch('services.reminder_service.datetime', MockDatetime):
        print("Testing reminder logic at 3:00 PM...")
        result = await rs.check_reminder_needed()
        print("Result:", result)

asyncio.run(main())
