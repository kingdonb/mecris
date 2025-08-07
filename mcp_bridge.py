#!/usr/bin/env python3
"""
Bridge between Claude Code's stdio MCP protocol and your HTTP FastAPI server
Save as: mcp_bridge.py
"""
import json
import sys
import requests
import subprocess
import time
import atexit
import os
from threading import Thread

class MCPBridge:
    def __init__(self):
        self.server_process = None
        self.base_url = "http://localhost:8000"
        
    def start_server(self):
        """Start the FastAPI server"""
        try:
            # Start your server process
            self.server_process = subprocess.Popen(
                ["make", "daemon"],
                cwd="/Users/yebyen/w/mecris",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for server to be ready
            for _ in range(30):  # Wait up to 30 seconds
                try:
                    response = requests.get(f"{self.base_url}/health", timeout=1)
                    if response.status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(1)
                
        except Exception as e:
            print(f"Failed to start server: {e}", file=sys.stderr)
            
    def stop_server(self):
        """Stop the FastAPI server"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            
    def handle_request(self, request):
        """Convert MCP request to HTTP and back"""
        try:
            method = request.get("method")
            
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "mecris", "version": "0.1.0"}
                    }
                }
                
            elif method == "tools/list":
                # Get tools from your HTTP endpoint
                response = requests.get(f"{self.base_url}/mcp/manifest")
                manifest = response.json()
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"tools": manifest.get("tools", [])}
                }
                
            elif method == "tools/call":
                # Forward tool call to your HTTP endpoint
                params = request.get("params", {})
                response = requests.post(f"{self.base_url}/mcp/call", json={
                    "tool": params.get("name"),
                    "parameters": params.get("arguments", {})
                })
                result = response.json()
                
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"content": [{"type": "text", "text": str(result.get("result", ""))}]}
                }
                
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -32601, "message": "Method not found"}
                }
                
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32603, "message": str(e)}
            }
    
    def run(self):
        """Main stdio loop"""
        self.start_server()
        atexit.register(self.stop_server)
        
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                    
                request = json.loads(line.strip())
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
                
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": str(e)}
                }
                print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    bridge = MCPBridge()
    bridge.run()
