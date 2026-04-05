import requests
import unittest
import os
import sys
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
        # We use a non-default port to avoid conflicts
        cls.server_proc = subprocess.Popen(
            [os.path.join(os.getcwd(), ".venv/bin/python3"), "-m", "uvicorn", "mcp_server:app", "--host", "127.0.0.1", "--port", "8001"],
            stdout=sys.stdout, # Direct output to parent stdout
            stderr=sys.stderr, # Direct output to parent stderr
            env={**os.environ.copy(), "MECRIS_MODE": "cloud", "DEFAULT_USER_ID": ""}
        )
        # Give it a few seconds to start
        time.sleep(5)
        cls.base_url = "http://127.0.0.1:8001"

    @classmethod
    def tearDownClass(cls):
        # Terminate the server process
        cls.server_proc.terminate()
        cls.server_proc.wait()

    def test_narrator_context_no_auth(self):
        """Verify that /narrator/context REJECTS requests without authentication."""
        session = requests.Session()
        response = session.get(f"{self.base_url}/narrator/context")
        if response.status_code != 401:
            print(f"FAILED: /narrator/context returned {response.status_code} with body: {response.text}")
        self.assertEqual(response.status_code, 401, "Endpoint should REQUIRE authentication")

    def test_beeminder_status_no_auth(self):
        """Verify that /beeminder/status REJECTS requests without authentication."""
        session = requests.Session()
        response = session.get(f"{self.base_url}/beeminder/status")
        self.assertEqual(response.status_code, 401, "Endpoint should REQUIRE authentication")

    def test_budget_status_no_auth(self):
        """Verify that /budget/status REJECTS requests without authentication."""
        session = requests.Session()
        response = session.get(f"{self.base_url}/budget/status")
        self.assertEqual(response.status_code, 401, "Endpoint should REQUIRE authentication")

if __name__ == "__main__":
    import sys
    unittest.main()
