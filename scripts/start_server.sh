#!/bin/bash

# Get the PORT environment variable or default to 8000
PORT=${PORT:-8000}

echo "Starting uvicorn server on host 0.0.0.0 port $PORT"

# Check if RELOAD environment variable is set to enable auto-reload
if [ "$RELOAD" = "true" ]; then
    echo "Auto-reload enabled (excluding cli/ directory)"
    exec python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT --reload
else
    # Start the application with the specified port (no reload)
    exec python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT
fi
