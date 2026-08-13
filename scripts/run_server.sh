#!/usr/bin/env bash
# Raspberry Pi Command Server Launch Script

cd "$(dirname "$0")/../server" || exit 1

HOST="${1:-0.0.0.0}"
PORT="${2:-5000}"

echo "Starting Raspberry Pi Command Server..."
python app.py
