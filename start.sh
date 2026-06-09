#!/bin/bash
export PYTHONPATH=$PYTHONPATH:/app

echo '1. NUKING DATABASE FOR CLEAN START...'
python -m backend.scripts.force_nuke_cloud_db

echo '2. Running Fresh Migrations...'
python -m backend.migrations.apply_all

echo '3. Seeding Official Users...'
python -m backend.scripts.seed_official_users

echo '4. Starting Nginx...'
nginx &

echo '5. Starting FastAPI...'
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
