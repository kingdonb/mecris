import asyncio
from py_harness.main import main
from unittest.mock import patch

async def try_it():
    # Patch input to provide one command and then exit
    with patch("builtins.input", side_effect=["get_narrator_context", "exit"]):
        await main()

if __name__ == "__main__":
    asyncio.run(try_it())
