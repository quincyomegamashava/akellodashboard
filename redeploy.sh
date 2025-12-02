#!/bin/bash

# Redeploy Akello Dashboard Script
# This script pulls the latest code and redeploys while preserving app.db

set -e  # Exit on any error

echo "=== Starting Akello Dashboard Redeployment ==="

# Backup the database
echo "Backing up app.db..."
cp app.db app.db.backup

# Stash any local changes
echo "Stashing local changes..."
git stash

# Pull latest changes from GitHub
echo "Pulling latest changes from GitHub..."
git pull origin main

# Restore the original database
echo "Restoring original app.db..."
mv app.db.backup app.db

# Stop and remove the old container
echo "Stopping old container..."
docker stop akello-dashboard-app || true
docker rm akello-dashboard-app || true

# Rebuild the Docker image
echo "Rebuilding Docker image..."
docker build -t akello-dashboard .

# Start the new container
echo "Starting new container..."
docker run -d --name akello-dashboard-app -p 5000:5000 akello-dashboard

# Verify the container is running
echo "Verifying container status..."
sleep 2
docker ps --filter name=akello-dashboard-app

echo "=== Redeployment Complete ==="
echo "Your app is running on port 5000 with your existing database"