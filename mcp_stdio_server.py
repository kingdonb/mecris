#!/usr/bin/env python3
"""
Mecris MCP Stdio Server
This script runs the Mecris MCP server in stdio mode for integration with Gemini CLI.
"""
import logging
import os
import sys
import time

from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Configure logging to a file to avoid interfering with stdio
log_file = os.getenv("MCP_STDIO_LOG_FILE", "/tmp/mecris_stdio.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file,
    filemode='w' # Overwrite log on each start
)
logger = logging.getLogger("mecris.stdio")

def main():
    """Main entry point for the stdio server."""
    logger.info("Starting Mecris MCP Server in stdio mode...")
    try:
        from mcp_server import mcp
        # mcp.run() by default uses stdio transport when no arguments are provided
        # and it's called in a way that it can detect the environment.
        mcp.run()

    except (KeyboardInterrupt, SystemExit):
        logger.info("Mecris MCP stdio server shutting down.")
    except Exception as e:
        logger.error(f"Mcp Stdio Server failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
