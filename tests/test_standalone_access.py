import requests
import unittest
import os
import signal
import subprocess
import time
from dotenv import load_dotenv

load_dotenv()

class TestStandaloneAccess(unittest.TestCase):
    """
    Test-Driven Generation (TDG) case to verify that the FastAPI endpoints
    in mcp_server.py ALLOW access without tokens when in STANDALONE mode.
    """

    @classmethod
    def setUpClass(cls):
        # Start the FastAPI server using uvicorn in STANDALONE mode
        cls.server_proc = subprocess.Popen(
            [os.path.join(os.getcwd(), ".venv/bin/python3"), "-m", "uvicorn", "mcp_server:app", "--host", "127.0.0.1", "--port", "8001"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ.copy(), "MECRIS_MODE": "standalone", "DEFAULT_USER_ID": "test-user"}
        )
        # Give it a few seconds to start
        time.sleep(5)
        cls.base_url = "http://127.0.0.1:8001"

    @classmethod
    def tearDownClass(cls):
        # Terminate the server process
        cls.server_proc.terminate()
        cls.server_proc.wait()

    def test_narrator_context_standalone(self):
        """Verify that /narrator/context ALLOWS access in standalone mode."""
        response = requests.get(f"{self.base_url}/narrator/context")
        self.assertEqual(response.status_code, 200)
        print("\n✅ [PASS] /narrator/context allowed access in standalone mode.")

    def test_health_check_public(self):
        """Verify that /health is always public."""
        response = requests.get(f"{self.base_url}/health")
        self.assertEqual(response.status_code, 200)
        print("✅ [PASS] /health is public.")

if __name__ == "__main__":
    import sys
    unittest.main()
