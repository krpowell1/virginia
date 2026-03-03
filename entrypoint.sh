#!/bin/bash
set -e

# Wait for Litestream to restore the database from S3 (if a replica exists).
# Litestream runs in a separate container and needs a moment to finish
# the restore-if-replica-exists step before the web app touches the DB.
echo "Waiting for Litestream restore..."
sleep 3

# Run database migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files into the shared volume (fast no-op if unchanged)
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting application..."
exec "$@"
