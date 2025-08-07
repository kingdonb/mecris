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
                try:
                    response = requests.get(f"{self.base_url}/mcp/manifest", timeout=5)
                    print(f"Manifest response status: {response.status_code}", file=sys.stderr)
                    print(f"Manifest response content: {response.text[:200]}...", file=sys.stderr)
                    
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
                    manifest = response.json()
                    tools = manifest.get("tools", [])
                    
                    # If no tools key, try to extract from a different format
                    if not tools and isinstance(manifest, list):
                        tools = manifest
                    elif not tools and "allowedTools" in manifest:
                        # Convert from your original format if needed
                        tools = [{"name": tool, "description": f"Tool: {tool}", "inputSchema": {"type": "object", "additionalProperties": True}} for tool in manifest["allowedTools"]]
                    
                    print(f"Returning {len(tools)} tools", file=sys.stderr)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {"tools": tools}
                    }
                except requests.RequestException as e:
                    print(f"Request error: {e}", file=sys.stderr)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32603, "message": f"Failed to fetch tools: {e}"}
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}", file=sys.stderr)
                    print(f"Response was: {response.text}", file=sys.stderr)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32603, "message": f"Invalid JSON response: {e}"}
                    }
                
            elif method == "tools/call":
                # Forward tool call to your HTTP endpoint
                params = request.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                print(f"Calling tool: {tool_name} with args: {arguments}", file=sys.stderr)
                
                try:
                    response = requests.post(f"{self.base_url}/mcp/call", json={
                        "tool": tool_name,
                        "parameters": arguments
                    }, timeout=10)
                    
                    print(f"Tool response status: {response.status_code}", file=sys.stderr)
                    print(f"Tool response: {response.text[:500]}...", file=sys.stderr)
                    
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
                    result = response.json()
                    
                    # Extract the actual result data
                    result_data = result.get("result", result)
                    
                    # Format as proper MCP response
                    if isinstance(result_data, dict):
                        # Pretty format JSON for better readability
                        formatted_result = json.dumps(result_data, indent=2, default=str)
                    else:
                        formatted_result = str(result_data)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text", 
                                    "text": formatted_result
                                }
                            ]
                        }
                    }
                    
                except requests.RequestException as e:
                    print(f"Request error calling tool: {e}", file=sys.stderr)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32603, "message": f"Tool call failed: {e}"}
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON decode error from tool response: {e}", file=sys.stderr)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32603, "message": f"Invalid JSON from tool: {e}"}
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
