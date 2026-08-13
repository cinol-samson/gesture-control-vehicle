#!/usr/bin/env bash
# Vision Client Launch Script

cd "$(dirname "$0")/../client" || exit 1

SERVER_IP="${1:-127.0.0.1}"
PORT="${2:-5000}"

echo "Starting Gesture Control Vision Client..."
python main.py --server-ip "$SERVER_IP" --port "$PORT"
