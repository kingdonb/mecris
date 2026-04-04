import asyncio
from mcp_server import get_daily_aggregate_status, get_language_velocity_stats, usage_tracker
from services.neon_sync_checker import NeonSyncChecker
import os

async def main():
    os.environ["DEFAULT_USER_ID"] = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"
    status = await get_daily_aggregate_status()
    
    if "error" in status:
        print(f"Error: {status['error']}")
        return

    print("\n===============================")
    print(f"   MECRIS AGGREGATE STATUS   ")
    print("===============================\n")
    
    print(f"Goal Score: {status['score']}")
    print(f"All Clear:  {status['all_clear']}")
    print("\nComponents:")
    print(f" - Walk Logged:  {'✅' if status['components']['walk'] else '❌'}")
    print(f" - Arabic Pace:  {'✅' if status['components']['arabic'] else '❌'}")
    print(f" - Greek Pace:   {'✅' if status['components']['greek'] else '❌'}")
    
    print("\n")
    if status['all_clear']:
        print(r"""
        .         *       .           *
     *       .  *    .       .    *
        .         *      *
             ,           ,          
            / \         / \         
           /   \       /   \        
          |     |     |     |       
        __|     |_____|     |__     
       |                       |    
       |  ✨ THE MAJESTY CAKE ✨|    
       |_______________________|    
       |                       |    
       |    CONGRATULATIONS!   |    
       |_______________________|    
       
       YOU ARE THE ACCOUNTABILITY MASTER.
       REST EASY.
        """)
    else:
        print(f"Your Majesty Cake is baking... ({status['score']})")
        print("Finish your remaining goals to earn your reward!")
        
if __name__ == "__main__":
    asyncio.run(main())
