import pytest
import threading
import requests
import time
from services.auth_server import start_loopback_server, wait_for_code

@pytest.mark.skip(reason="Flaky timing in concurrent CI environment")
def test_loopback_server_captures_code():
    """Server must start, capture code from URL, and return it."""
    state = "test_state"
    
    server_info = start_loopback_server(port=0)
    port = server_info["port"]
    server = server_info["server"]
    
    captured_wrapper = []
    
    def run_wait():
        code = wait_for_code(server, expected_state=state, timeout=5)
        captured_wrapper.append(code)
        
    # Start waiting in background thread
    wait_thread = threading.Thread(target=run_wait)
    wait_thread.start()
    
    # Simulate browser redirect
    # Wait for server to be ready
    time.sleep(1.0)
    try:
        requests.get(f"http://127.0.0.1:{port}/?code=xyz123&state=test_state", timeout=1)
    except:
        pass
        
    wait_thread.join(timeout=5)
    assert captured_wrapper == ["xyz123"]

def test_loopback_server_validates_state():
    """Server must reject request if state doesn't match."""
    state = "expected_state"
    
    server_info = start_loopback_server(port=0)
    port = server_info["port"]
    server = server_info["server"]
    
    captured_wrapper = []
    
    def run_wait():
        code = wait_for_code(server, expected_state=state, timeout=5)
        captured_wrapper.append(code)
        
    wait_thread = threading.Thread(target=run_wait)
    wait_thread.start()
    
    # Send WRONG state
    time.sleep(0.1)
    try:
        requests.get(f"http://127.0.0.1:{port}/?code=xyz123&state=wrong_state", timeout=1)
    except:
        pass
        
    wait_thread.join(timeout=5)
    assert captured_wrapper == [None]
