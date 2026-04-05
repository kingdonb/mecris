import sys
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

logger = logging.getLogger("mecris.auth_server")

class AuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        # Ignore irrelevant requests like favicon
        if "code=" not in self.path and "state=" not in self.path:
            self.send_response(404)
            self.end_headers()
            return

        # Use urlparse on self.path to get the query string
        parsed_path = urlparse(self.path)
        query = parse_qs(parsed_path.query)
        
        code = query.get('code', [None])[0]
        state = query.get('state', [None])[0]
        
        self.server.captured_code = code
        self.server.captured_state = state
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        success_msg = """
        <html>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #00C853;">✅ Login Successful</h1>
                <p>You can now close this window and return to your terminal.</p>
            </body>
        </html>
        """
        self.wfile.write(success_msg.encode('utf-8'))
        
        # Signal that we have received a potential auth response
        if hasattr(self.server, 'completion_event'):
            self.server.completion_event.set()

def start_loopback_server(port: int = 0) -> dict:
    """
    Start a temporary loopback server to capture the OIDC redirect.
    Returns a dict with 'server' and 'port'.
    """
    server = HTTPServer(('127.0.0.1', port), AuthHandler)
    server.captured_code = None
    server.captured_state = None
    server.completion_event = threading.Event()
    
    return {
        "server": server,
        "port": server.server_port
    }

def wait_for_code(server: HTTPServer, expected_state: str, timeout: int = 300) -> str:
    """Run the server and block until a code is captured or timeout."""
    def run_server():
        server.serve_forever()
        
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Wait for the event (triggered in do_GET)
    success = server.completion_event.wait(timeout=timeout)
    
    # Shutdown cleanly
    server.shutdown()
    server_thread.join()
    
    if not success:
        logger.warning("Auth server: Timed out waiting for redirect.")
        return None
        
    if server.captured_state != expected_state:
        logger.warning(f"Auth server: State mismatch. Expected {expected_state}, got {server.captured_state}")
        return None
        
    return server.captured_code
