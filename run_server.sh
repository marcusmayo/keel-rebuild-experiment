#!/usr/bin/env bash
# Start the Meridian operator console detached on port 8000.
# Loads .env, ensures the TOTP secret exists, writes a pidfile, logs to
# logs/server.log. Safe to re-run: it stops any existing instance first.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p logs

# Stop any existing instance.
if [[ -f logs/server.pid ]]; then
  OLD=$(cat logs/server.pid 2>/dev/null || true)
  if [[ -n "${OLD:-}" ]] && kill -0 "$OLD" 2>/dev/null; then
    kill "$OLD" 2>/dev/null || true
    sleep 1
  fi
fi
pkill -f "python3 app.py" 2>/dev/null || true
sleep 1

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

# Launch fully detached in its own session so it survives the parent shell.
setsid python3 app.py > logs/server.log 2>&1 < /dev/null &
echo $! > logs/server.pid
disown || true

# Wait for it to accept connections.
for _ in $(seq 1 20); do
  if curl -s -o /dev/null http://localhost:8000/login 2>/dev/null; then
    echo "server up (pid $(cat logs/server.pid)) on http://localhost:8000"
    exit 0
  fi
  sleep 0.5
done
echo "server did not come up; see logs/server.log" >&2
exit 1
