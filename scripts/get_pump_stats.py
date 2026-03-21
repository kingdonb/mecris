import asyncio
import json
from scripts.clozemaster_scraper import sync_clozemaster_to_beeminder

async def main():
    try:
        data = await sync_clozemaster_to_beeminder(dry_run=True)
        print(json.dumps(data))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    asyncio.run(main())
