#!/usr/bin/env python3
"""
Mecris MCP Server Startup Script
Handles initialization, health checks, and graceful startup
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.getenv("LOG_FILE", "mecris.log"))
    ]
)

logger = logging.getLogger("mecris.startup")

async def check_dependencies():
    """Check if all required services are available"""
    logger.info("Checking system dependencies...")
    
    issues = []
    
    # Check environment variables
    required_env = [
        "OBSIDIAN_VAULT_PATH",
        "BEEMINDER_USERNAME", 
        "BEEMINDER_AUTH_TOKEN",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN"
    ]
    
    for env_var in required_env:
        if not os.getenv(env_var):
            issues.append(f"Missing environment variable: {env_var}")
    
    # Try importing our modules
    try:
        from obsidian_client import ObsidianMCPClient
        from beeminder_client import BeeminderClient
        from twilio_sender import send_sms
        logger.info("✅ All modules imported successfully")
    except ImportError as e:
        issues.append(f"Import error: {e}")
    
    # Test external service connectivity
    try:
        obsidian = ObsidianMCPClient()
        obsidian_status = await obsidian.health_check()
        logger.info(f"Obsidian MCP: {obsidian_status}")
        if obsidian_status != "ok":
            issues.append(f"Obsidian MCP not healthy: {obsidian_status}")
        await obsidian.close()
    except Exception as e:
        issues.append(f"Obsidian health check failed: {e}")
    
    try:
        beeminder = BeeminderClient()
        beeminder_status = await beeminder.health_check()
        logger.info(f"Beeminder API: {beeminder_status}")
        if beeminder_status not in ["ok", "not_configured"]:
            issues.append(f"Beeminder API not healthy: {beeminder_status}")
        await beeminder.close()
    except Exception as e:
        issues.append(f"Beeminder health check failed: {e}")
    
    if issues:
        logger.warning("⚠️ Startup issues detected:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        
        # Skip interactive prompt for background execution
        if os.getenv("SKIP_HEALTH_PROMPT", "false").lower() == "true":
            logger.warning("Continuing with degraded services (SKIP_HEALTH_PROMPT=true)")
        elif input("Continue anyway? (y/N): ").lower() != 'y':
            sys.exit(1)
    else:
        logger.info("✅ All health checks passed")

@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan manager"""
    logger.info("🧠 Mecris MCP Server starting up...")
    await check_dependencies()
    
    # Send startup notification
    try:
        from twilio_sender import send_sms
        await asyncio.create_task(
            asyncio.to_thread(send_sms, "🧠 Mecris narrator is online and monitoring your goals.")
        )
    except Exception as e:
        logger.warning(f"Failed to send startup notification: {e}")
    
    yield
    
    logger.info("🧠 Mecris MCP Server shutting down...")
    
    # Send shutdown notification
    try:
        from twilio_sender import send_sms
        await asyncio.create_task(
            asyncio.to_thread(send_sms, "🧠 Mecris narrator going offline.")
        )
    except Exception as e:
        logger.warning(f"Failed to send shutdown notification: {e}")

def main():
    """Main entry point"""
    # Ensure we're using the correct Python executable
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Python version: {sys.version}")
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")  # Secure localhost binding by default
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting Mecris MCP Server on {host}:{port}")
    logger.info(f"Debug mode: {debug}")
    
    # Import app with lifespan
    from mcp_server import app
    app.router.lifespan_context = lifespan
    
    # Start server
    uvicorn.run(
        "mcp_server:app",
        host=host,
        port=port,
        reload=debug,
        log_level=log_level.lower(),
        access_log=debug
    )

if __name__ == "__main__":
    try:
        main()  # main() is not async anymore since uvicorn.run handles it
    except KeyboardInterrupt:
        logger.info("👋 Mecris shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Mecris startup failed: {e}")
        sys.exit(1)