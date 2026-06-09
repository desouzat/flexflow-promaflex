#!/bin/bash
export PYTHONPATH=$PYTHONPATH:/app
export PYTHONUNBUFFERED=1

echo '1. Starting Nginx...'
nginx &

echo '2. Starting FastAPI with Gunicorn (BYPASSING SEEDING)...'
# No more migrations, no more seeding. Just start the server.
exec gunicorn backend.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 90
