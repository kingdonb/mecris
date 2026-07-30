"""
Simple unified entry point - runs HTTP and MCP in same event loop.
"""
import os
import sys
import logging
import asyncio

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True,
)
logger = logging.getLogger("mecris")

def log(msg):
    print(f"[MECRIS] {msg}", file=sys.stderr, flush=True)

log(f"Starting, argv={sys.argv}, pid={os.getpid()}")

# Import AFTER logging setup
from mcp.server.fastmcp import FastMCP
import uvicorn
from dotenv import load_dotenv

# Load env
load_dotenv()

# Import the app and mcp from the existing module
# We need to import them from the current module's context
# Let's just run the server directly

async def main():
    use_stdio = "--stdio" in sys.argv
    
    # Import the FastMCP and FastAPI app
    # These are defined in mcp_server.py at module level
    from mcp_server import mcp, app, scheduler
    from services.walk_cache_listener import start_walk_cache_listener, set_cache_reference
    from mcp_server import daily_activity_cache
    
    log("Starting scheduler")
    scheduler.start()
    
    # Walk cache listener
    try:
        set_cache_reference(daily_activity_cache)
        asyncio.create_task(start_walk_cache_listener())
        log("Walk cache listener started")
    except Exception as e:
        log(f"Walk cache listener not started: {e}")
    
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="error",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    
    if "--stdio" in sys.argv:
        log("Running HTTP server + MCP stdio in same event loop")
        await asyncio.gather(
            server.serve(),
            mcp.run_stdio_async(),
        )
    else:
        log("Running HTTP server only")
        await server.serve()
    
    # Cleanup
    log("Shutting down scheduler")
    scheduler.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log(f"SERVER ERROR: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
