#!/usr/bin/env bash

# Find if .venv exists
if [ -d ".venv" ]; then
    echo "Virtual environment found. Activating..."
    source .venv/bin/activate
fi

python3 server.py