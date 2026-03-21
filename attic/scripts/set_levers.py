import asyncio
from services.neon_sync_checker import NeonSyncChecker

async def main():
    neon = NeonSyncChecker()
    # Set Arabic to Aggressive (4x)
    neon.update_pump_multiplier("arabic", 4.0)
    # Set Greek to Steady (2x)
    neon.update_pump_multiplier("greek", 2.0)
    print("Multipliers updated.")

if __name__ == "__main__":
    asyncio.run(main())
