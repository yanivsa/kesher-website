import sys
import subprocess
import json
import time
import os

env = os.environ.copy()
api_key = env.get("COMPOSIO_API_KEY")
if not api_key:
    print("Error: COMPOSIO_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)
env["PATH"] = "/Users/ninja/.nvm/versions/node/v22.21.1/bin:" + env.get("PATH", "")

proc = subprocess.Popen(
    ['npx', '-y', '@composio/cli', 'serve', 'mcp'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True,
    bufsize=1
)

print("Started process. Waiting 15 seconds...")
time.sleep(15)
# Check if process is still running
status = proc.poll()
print("Process exit code:", status)

# Read stderr and stdout
import fcntl
for pipe in [proc.stdout, proc.stderr]:
    fd = pipe.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

try:
    stdout_content = proc.stdout.read()
    print("STDOUT:", stdout_content)
except Exception as e:
    print("STDOUT read error:", e)

try:
    stderr_content = proc.stderr.read()
    print("STDERR:", stderr_content)
except Exception as e:
    print("STDERR read error:", e)

if proc.poll() is None:
    proc.terminate()
