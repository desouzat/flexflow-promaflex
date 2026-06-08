#!/bin/sh
set -e

# Run database migrations
echo 'Running database migrations...'
python -m backend.migrations.apply_all

# Start Uvicorn FastAPI backend in the background
echo 'Starting FastAPI backend...'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 2 &

# Start Nginx in the foreground
echo 'Starting Nginx proxy...'
exec nginx -g "daemon off;"
