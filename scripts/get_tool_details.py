import subprocess
import json
import time

proc = subprocess.Popen(
    ['node', '/Users/ninja/.npm/_npx/32a74c6d3fc3e52a/node_modules/@roomi-fields/notebooklm-mcp/dist/index.js'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

def read_until_id(proc, req_id):
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            data = json.loads(line.strip())
            if data.get("id") == req_id:
                return data
        except Exception:
            pass
    return None

# Initialize
proc.stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"},
        "protocolVersion": "2024-11-05"
    },
    "id": 0
}) + "\n")
proc.stdin.flush()

read_until_id(proc, 0)

# initialized notification
proc.stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
}) + "\n")
proc.stdin.flush()

# Call tools/list
proc.stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
}) + "\n")
proc.stdin.flush()

resp = read_until_id(proc, 1)
if resp:
    tools = resp.get("result", {}).get("tools", [])
    for t in tools:
        if t["name"] in ["source_add", "content_generate", "content_download"]:
            print("TOOL:", t["name"])
            print(json.dumps(t.get("inputSchema"), indent=2, ensure_ascii=False))
            print("-" * 50)

proc.terminate()
