import subprocess
import json
import time
import os
import sys

class NotebookLMClient:
    def __init__(self):
        # Path to the compiled JS script of the MCP server
        self.server_path = '/Users/ninja/.npm/_npx/32a74c6d3fc3e52a/node_modules/@roomi-fields/notebooklm-mcp/dist/index.js'
        self.proc = None
        self.id_counter = 1

    def connect(self):
        print("Connecting to NotebookLM MCP Server...")
        self.proc = subprocess.Popen(
            ['/Users/ninja/.nvm/versions/node/v22.21.1/bin/node', self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # 1. Send initialize
        init_id = self.id_counter
        self.id_counter += 1
        init_msg = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "capabilities": {},
                "clientInfo": {"name": "python-client", "version": "1.0"},
                "protocolVersion": "2024-11-05"
            },
            "id": init_id
        }
        self._write_line(init_msg)
        
        # Read response for initialize
        init_resp = self._read_response(init_id)
        if not init_resp:
            raise Exception("Failed to initialize MCP Server (no response)")
            
        # 2. Send initialized notification (no ID, it is a notification)
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        self._write_line(initialized_msg)
        print("MCP Handshake Completed.")

    def call_tool(self, name, arguments=None, timeout=300):
        if not self.proc:
            raise Exception("Client not connected. Call connect() first.")
            
        call_id = self.id_counter
        self.id_counter += 1
        
        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {}
            },
            "id": call_id
        }
        
        print(f"Calling tool: {name}...")
        self._write_line(req)
        
        # Read tool response
        resp = self._read_response(call_id, timeout=timeout)
        if not resp:
            raise Exception(f"No response received for tool {name}")
            
        if "error" in resp:
            raise Exception(f"Tool {name} returned error: {resp['error']}")
            
        return resp.get("result")

    def disconnect(self):
        if self.proc:
            print("Disconnecting from MCP Server...")
            self.proc.terminate()
            self.proc.wait()
            self.proc = None

    def _write_line(self, obj):
        line = json.dumps(obj) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def _read_response(self, expected_id, timeout=30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            line = self.proc.stdout.readline()
            if not line:
                # Check if process died
                if self.proc.poll() is not None:
                    raise Exception("MCP Server process terminated unexpectedly")
                time.sleep(0.1)
                continue
            
            # Print server logs if they are outputted as warnings or info (optional)
            # Typically standard JSON-RPC responses have "id" or "method" (for notifications)
            try:
                msg = json.loads(line.strip())
                # Check if it is a response to our ID
                if msg.get("id") == expected_id:
                    return msg
                # If it is a log message or notification, we can print it
                if "method" in msg and msg["method"] == "notifications/message":
                    print(f"[MCP LOG]: {msg.get('params', {}).get('message')}")
            except Exception:
                # Could be a plain text print, ignore or print for debug
                pass
        return None

if __name__ == "__main__":
    # Test client
    client = NotebookLMClient()
    try:
        client.connect()
        # List notebooks
        result = client.call_tool("notebook_list")
        print("Notebooks found:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        client.disconnect()
