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

# Set non-blocking on stderr
fd_err = proc.stderr.fileno()
fl_err = fcntl.fcntl(fd_err, fcntl.F_GETFL)
fcntl.fcntl(fd_err, fcntl.F_SETFL, fl_err | os.O_NONBLOCK)

# Set non-blocking on stdout
fd_out = proc.stdout.fileno()
fl_out = fcntl.fcntl(fd_out, fcntl.F_GETFL)
fcntl.fcntl(fd_out, fcntl.F_SETFL, fl_out | os.O_NONBLOCK)

def write_msg(msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()

def read_and_print_all(timeout_secs=60):
    start = time.time()
    while time.time() - start < timeout_secs:
        # Read stdout
        try:
            line = proc.stdout.readline()
            if line:
                print(f"[STDOUT]: {line.strip()}")
        except Exception:
            pass
            
        # Read stderr
        try:
            err = proc.stderr.read()
            if err:
                print(f"[STDERR]: {err.strip()}")
        except Exception:
            pass
            
        time.sleep(0.1)

# Handshake
print("Sending initialize...")
write_msg({
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "capabilities": {},
        "clientInfo": {"name": "debug", "version": "1.0"},
        "protocolVersion": "2024-11-05"
    },
    "id": 0
})

time.sleep(2)
read_and_print_all(2)

print("Sending initialized...")
write_msg({
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
})

time.sleep(1)
read_and_print_all(1)

print("\n--- Triggering content_generate ---")
write_msg({
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "content_generate",
        "arguments": {
            "content_type": "audio_overview",
            "notebook_url": "https://notebooklm.google.com/notebook/e101e7d7-5305-45b3-a611-21a5475ceb63?hl=en",
            "custom_instructions": "תייצר סרטון ויראלי בעברית (ללא שימוש בשמות המקור, השתמש בשמות טליה ואדם) על פי המקור החדש. גרסה אלטרנטיבית לסרטון Faceless, עם זווית ראייה שונה ומקרה שונה. הוידאו מיועד לערוץ יוטיוב קשר ייעוץ זוגי."
        }
    },
    "id": 1
})

# Let it run for 120 seconds and print all logs
read_and_print_all(120)

proc.terminate()
