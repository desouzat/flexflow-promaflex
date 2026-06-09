#!/bin/bash
export PYTHONPATH=$PYTHONPATH:/app
export PYTHONUNBUFFERED=1

echo '1. Running Status Constraints Fix Migration...'
python backend/migrations/fix_status_constraints.py

echo '2. Running Admin Seeder...'
python backend/scripts/create_admin_user.py

echo '3. Starting Nginx...'
nginx &

echo '4. Starting FastAPI with Gunicorn (BYPASSING OTHER SEEDING)...'
# No more hanging migrations or seeders. Just start the server.
exec gunicorn backend.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 90
