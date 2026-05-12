#!/bin/bash

# Redeploy Akello Dashboard Script
# This script pulls the latest code and redeploys while preserving app.db

set -e  # Exit on any error

echo "=== Starting Akello Dashboard Redeployment ==="

# Backup the database before any operations
BACKUP_FILE=""
if [ -f "app.db" ]; then
    echo "Backing up app.db..."
    BACKUP_DIR="backups"
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/app.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp app.db "$BACKUP_FILE"
    echo "Database backed up to $BACKUP_FILE"
else
    echo "Warning: app.db not found. Skipping backup."
fi

# Stash any local changes
echo "Stashing local changes..."
git stash

# Pull latest changes from GitHub
echo "Pulling latest changes from GitHub..."
git pull origin main

# Restore the original database if it was overwritten by git pull
if [ -f "app.db.backup" ]; then
    echo "Restoring original app.db from backup..."
    mv app.db.backup app.db
elif [ ! -f "app.db" ] && [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
    echo "Restoring app.db from timestamped backup..."
    cp "$BACKUP_FILE" app.db
    echo "Database restored from $BACKUP_FILE"
fi

# Stop and remove the old container
echo "Stopping old container..."
docker stop akello-dashboard-app || true
docker rm akello-dashboard-app || true

# Rebuild the Docker image
echo "Rebuilding Docker image..."
docker build -t akello-dashboard .

# Start the new container with volume mounts for database and .env file persistence
echo "Starting new container with database and .env file mounts..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker run -d --name akello-dashboard-app -p 5000:5000 \
  -v "$SCRIPT_DIR/app.db:/app/app.db" \
  -v "$SCRIPT_DIR/.env:/app/.env" \
  akello-dashboard

# Verify the container is running
echo "Verifying container status..."
sleep 2
if docker ps --filter name=akello-dashboard-app --format "{{.Names}}" | grep -q akello-dashboard-app; then
    echo "✓ Container is running"
else
    echo "✗ Container failed to start. Check logs with: docker logs akello-dashboard-app"
    exit 1
fi

# Verify database file is accessible
echo "Verifying database file..."
if [ -f "app.db" ]; then
    DB_SIZE=$(stat -f%z "app.db" 2>/dev/null || stat -c%s "app.db" 2>/dev/null || echo "unknown")
    echo "✓ Database file exists (size: $DB_SIZE bytes)"
    
    # Check if database is mounted in container
    if docker exec akello-dashboard-app test -f /app/app.db 2>/dev/null; then
        echo "✓ Database file is accessible inside container"
    else
        echo "⚠ Warning: Database file may not be accessible inside container"
    fi
else
    echo "⚠ Warning: app.db not found on host"
fi

echo "=== Redeployment Complete ==="
echo "Your app is running on port 5000 with your existing database"