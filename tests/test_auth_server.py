import pytest
import threading
import requests
import time
from services.auth_server import start_loopback_server

def test_loopback_server_captures_code():
    """Server must start, capture code from URL, and return it."""
    state = "test_state"
    captured_code = []
    
    def run_server():
        code = start_loopback_server(expected_state=state, port=0, timeout=5)
        captured_code.append(code)
        
    # Start server in background thread
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    
    # Wait for server to start (we need to find which port it's on)
    # Since we can't easily find the random port in this draft, 
    # we'll fix the port for the test.
    time.sleep(1) 
    
    # Simulate browser redirect
    # Assuming the server is on localhost:54321 for this test case
    try:
        requests.get("http://localhost:54321/?code=xyz123&state=test_state")
    except:
        pass
        
    server_thread.join(timeout=5)
    assert "xyz123" in captured_code

def test_loopback_server_validates_state():
    """Server must reject request if state doesn't match."""
    # Implementation pending...
    pass
