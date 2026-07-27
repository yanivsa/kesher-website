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
    # Print everything while reading
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        print("[STDOUT]:", line.strip())
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
        "clientInfo": {"name": "debug-client", "version": "1.0"},
        "protocolVersion": "2024-11-05"
    },
    "id": 0
}) + "\n")
proc.stdin.flush()
read_until_id(proc, 0)

proc.stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
}) + "\n")
proc.stdin.flush()

# Let's call content_generate with audio_overview
print("\n--- Triggering content_generate ---")
proc.stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "content_generate",
        "arguments": {
            "content_type": "audio_overview",
            "notebook_url": "https://notebooklm.google.com/notebook/e101e7d7-5305-45b3-a611-21a5475ceb63",
            "custom_instructions": "תייצר סרטון ויראלי בעברית (ללא שימוש בשמות המקור, השתמש בשמות טליה ואדם) על פי המקור החדש. גרסה אלטרנטיבית לסרטון Faceless, עם זווית ראייה שונה ומקרה שונה. הוידאו מיועד לערוץ יוטיוב קשר ייעוץ זוגי."
        }
    },
    "id": 1
}) + "\n")
proc.stdin.flush()

# Wait and print stderr/stdout logs to see what's happening
# Set non-blocking to print stderr logs as well
import os
import fcntl
fd = proc.stderr.fileno()
fl = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

start_time = time.time()
while time.time() - start_time < 90: # Wait up to 90 seconds
    line = proc.stdout.readline()
    if line:
        print("[STDOUT]:", line.strip())
        try:
            data = json.loads(line.strip())
            if data.get("id") == 1:
                print("FINISHED tool call with:", data)
                break
        except Exception:
            pass
            
    try:
        err = proc.stderr.read()
        if err:
            print("[STDERR]:", err.strip())
    except Exception:
        pass
        
    time.sleep(0.5)

proc.terminate()
