import requests
import unittest
import os
import signal
import subprocess
import time
from dotenv import load_dotenv

load_dotenv()

class TestUnauthorizedAccess(unittest.TestCase):
    """
    Test-Driven Generation (TDG) case to verify that the FastAPI endpoints
    in mcp_server.py are unauthorized and leak data.
    """

    @classmethod
    def setUpClass(cls):
        # Start the FastAPI server using uvicorn
        # We use a non-default port to avoid conflicts, but the test assumes 8000.
        cls.server_proc = subprocess.Popen(
            [os.path.join(os.getcwd(), ".venv/bin/python3"), "-m", "uvicorn", "mcp_server:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy()
        )
        # Give it a few seconds to start
        time.sleep(5)
        cls.base_url = "http://127.0.0.1:8000"

    @classmethod
    def tearDownClass(cls):
        # Terminate the server process
        cls.server_proc.terminate()
        cls.server_proc.wait()

    def test_narrator_context_no_auth(self):
        """Verify that /narrator/context REJECTS requests without authentication."""
        response = requests.get(f"{self.base_url}/narrator/context")
        self.assertEqual(response.status_code, 401, "Endpoint should REQUIRE authentication")
        print("\n✅ [PASS] /narrator/context correctly rejected unauthorized request.")

    def test_beeminder_status_no_auth(self):
        """Verify that /beeminder/status REJECTS requests without authentication."""
        response = requests.get(f"{self.base_url}/beeminder/status")
        self.assertEqual(response.status_code, 401, "Endpoint should REQUIRE authentication")
        print("✅ [PASS] /beeminder/status correctly rejected unauthorized request.")

    def test_budget_status_no_auth(self):
        """Verify that /budget/status REJECTS requests without authentication."""
        response = requests.get(f"{self.base_url}/budget/status")
        self.assertEqual(response.status_code, 401, "Endpoint should REQUIRE authentication")
        print("✅ [PASS] /budget/status correctly rejected unauthorized request.")

if __name__ == "__main__":
    import sys
    unittest.main()
