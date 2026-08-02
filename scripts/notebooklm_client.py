import subprocess
import json
import time
import os
import sys
import signal


class NotebookLMTimeoutError(TimeoutError):
    """A bounded NotebookLM MCP operation did not produce a response."""

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
            bufsize=1,
            start_new_session=True,
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
        init_resp = self._read_response(init_id, timeout=45)
        if not init_resp:
            raise NotebookLMTimeoutError("NotebookLM MCP initialization timed out after 45 seconds")
            
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
            raise NotebookLMTimeoutError(
                f"NotebookLM tool {name} timed out after {timeout} seconds"
            )
            
        if "error" in resp:
            raise Exception(f"Tool {name} returned error: {resp['error']}")
            
        return resp.get("result")

    def disconnect(self):
        if self.proc:
            print("Disconnecting from MCP Server...")
            descendants = self._descendant_pids(self.proc.pid)
            for pid in reversed(descendants):
                self._signal_if_alive(pid, signal.SIGTERM)
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print("NotebookLM MCP did not exit cleanly; killing it.")
                    for pid in reversed(descendants):
                        self._signal_if_alive(pid, signal.SIGKILL)
                    self.proc.kill()
                    self.proc.wait(timeout=10)
            self.proc = None

    @staticmethod
    def _descendant_pids(parent_pid):
        """Return the MCP server's current child-process tree, deepest first."""
        descendants = []
        pending = [parent_pid]
        while pending:
            pid = pending.pop()
            result = subprocess.run(
                ["pgrep", "-P", str(pid)], capture_output=True, text=True, check=False
            )
            children = [int(value) for value in result.stdout.split() if value.isdigit()]
            descendants.extend(children)
            pending.extend(children)
        return descendants

    @staticmethod
    def _signal_if_alive(pid, sig):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    def _write_line(self, obj):
        line = json.dumps(obj) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def _read_response(self, expected_id, timeout=30):
        import select
        start_time = time.time()
        while time.time() - start_time < timeout:
            rlist, _, _ = select.select([self.proc.stdout], [], [], 1.0)
            if not rlist:
                if self.proc.poll() is not None:
                    raise Exception("MCP Server process terminated unexpectedly")
                continue
            line = self.proc.stdout.readline()
            if not line:
                # Check if process died
                if self.proc.poll() is not None:
                    raise Exception("MCP Server process terminated unexpectedly")
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
