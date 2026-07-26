import subprocess
import json
import time
import os
import fcntl

proc = subprocess.Popen(
    ['node', '/Users/ninja/.npm/_npx/32a74c6d3fc3e52a/node_modules/@roomi-fields/notebooklm-mcp/dist/index.js'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

# Initialize
init_msg = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"},
        "protocolVersion": "2024-11-05"
    },
    "id": 0
}

proc.stdin.write(json.dumps(init_msg) + "\n")
proc.stdin.flush()

time.sleep(3)

# Set non-blocking
for pipe in [proc.stdout, proc.stderr]:
    fd = pipe.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

stdout_content = ""
try:
    content = proc.stdout.read()
    if content:
        stdout_content = content
except Exception:
    pass

stderr_content = ""
try:
    content = proc.stderr.read()
    if content:
        stderr_content = content
except Exception:
    pass

print("STDOUT:")
print(stdout_content)
print("\nSTDERR:")
print(stderr_content)

proc.terminate()
