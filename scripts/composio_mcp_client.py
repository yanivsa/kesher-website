import subprocess
import json
import time
import os
import select
import getpass


KEYCHAIN_SERVICE = "kesher-composio-api-key"


def load_composio_api_key():
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if api_key:
        return api_key

    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                getpass.getuser(),
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        result = None

    if result and result.stdout.strip():
        return result.stdout.strip()

    raise RuntimeError(
        "COMPOSIO_API_KEY is not configured. Set it in the environment or "
        f"store it in macOS Keychain service {KEYCHAIN_SERVICE!r}."
    )

class ComposioMCPClient:
    def __init__(self):
        self.proc = None
        self.id_counter = 1

    def connect(self):
        print("Connecting to @composio/mcp Server via connect.composio.dev...")
        env = os.environ.copy()
        env["COMPOSIO_API_KEY"] = load_composio_api_key()
        
        self.proc = subprocess.Popen(
            ['npx', '-y', '@composio/mcp', 'start', '--url', 'https://connect.composio.dev/mcp'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1
        )
        
        # Initialize
        init_id = self.id_counter
        self.id_counter += 1
        init_msg = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
                "protocolVersion": "2024-11-05"
            },
            "id": init_id
        }
        self._write_line(init_msg)
        
        # Read init response
        init_resp = self._read_response(init_id, timeout=180)
        if not init_resp:
            raise Exception("Failed to initialize Composio MCP Server (no response)")
            
        # Send initialized notification
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        self._write_line(initialized_msg)
        print("Composio MCP Handshake Completed.")

    def call_tool(self, name, arguments=None, timeout=120):
        if not self.proc:
            raise Exception("Client not connected.")
            
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
        
        print(f"Calling Composio tool: {name}...")
        self._write_line(req)
        
        resp = self._read_response(call_id, timeout=timeout)
        if not resp:
            raise Exception(f"No response received for tool {name}")
            
        if "error" in resp:
            raise Exception(f"Tool {name} returned error: {resp['error']}")
            
        return resp.get("result")

    def disconnect(self):
        if self.proc:
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
            ready, _, _ = select.select([self.proc.stdout], [], [], 0.2)
            if not ready:
                if self.proc.poll() is not None:
                    # Let's read stderr to print error
                    err_msg = ""
                    try:
                        import fcntl
                        fd = self.proc.stderr.fileno()
                        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                        err_msg = self.proc.stderr.read() or ""
                    except Exception:
                        pass
                    raise Exception(f"Composio MCP process terminated unexpectedly. Stderr: {err_msg}")
                continue
            line = self.proc.stdout.readline()
            if not line:
                continue
            
            try:
                msg = json.loads(line.strip())
                if msg.get("id") == expected_id:
                    return msg
            except Exception:
                pass
        return None

if __name__ == "__main__":
    client = ComposioMCPClient()
    try:
        client.connect()
        # List tools
        call_id = client.id_counter
        client.id_counter += 1
        client._write_line({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": call_id
        })
        resp = client._read_response(call_id, timeout=30)
        if resp:
            tools = resp.get("result", {}).get("tools", [])
            print(f"Success! Listed {len(tools)} tools.")
            # Search for youtube tools
            youtube_tools = [t for t in tools if "youtube" in t["name"].lower()]
            print("YouTube tools:")
            for yt in youtube_tools:
                print(f"- {yt['name']}: {yt.get('description', '')[:100]}...")
                print(f"  Input Schema: {list(yt.get('inputSchema', {}).get('properties', {}).keys())}")
        else:
            print("Failed to list tools.")
    finally:
        client.disconnect()
