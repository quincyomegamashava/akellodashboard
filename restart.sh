#!/bin/bash

# Restart Akello Dashboard Script
# This script restarts the Docker container and Flask app without rebuilding or pulling changes

set -e  # Exit on any error

echo "=== Restarting Akello Dashboard ==="

CONTAINER_NAME="akello-dashboard-app"

# Get script directory for volume mounts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if container exists
if docker ps -a --filter name=$CONTAINER_NAME --format "{{.Names}}" | grep -q $CONTAINER_NAME; then
    # Container exists, restart it to reload Flask and pick up .env changes
    echo "Restarting container to reload Flask application and environment variables..."
    docker restart $CONTAINER_NAME
    echo "✓ Container restarted - Flask app will reload and pick up .env changes"
else
    # Container doesn't exist, create it with app.db and .env mounts
    echo "Container not found. Creating new container with database and .env mounts..."
    docker run -d --name $CONTAINER_NAME -p 5000:5000 \
      -v "$SCRIPT_DIR/app.db:/app/app.db" \
      -v "$SCRIPT_DIR/.env:/app/.env" \
      akello-dashboard
    echo "✓ Container created and started with .env file mounted"
fi

# Verify the container is running
echo "Verifying container status..."
sleep 2
if docker ps --filter name=$CONTAINER_NAME --format "{{.Names}}" | grep -q $CONTAINER_NAME; then
    echo "✓ Container is running"
    
    # Verify .env file is accessible in container
    if [ -f "$SCRIPT_DIR/.env" ]; then
        if docker exec $CONTAINER_NAME test -f /app/.env 2>/dev/null; then
            echo "✓ .env file is accessible inside container"
        else
            echo "⚠ Warning: .env file exists on host but is not accessible in container"
            echo "  The container may need to be recreated with the .env mount."
            echo "  Run: ./redeploy.sh to recreate the container with proper mounts"
        fi
    else
        echo "⚠ Warning: .env file not found on host at $SCRIPT_DIR/.env"
    fi
    
    echo "✓ Flask app should be accessible on port 5000"
    echo ""
    echo "=== Restart Complete ==="
    echo "Your app is running on http://localhost:5000"
    echo "Note: If .env changes aren't being picked up, the container may need to be"
    echo "      recreated. Run ./redeploy.sh to ensure the container has the .env mount."
else
    echo "✗ Container failed to start. Check logs with: docker logs $CONTAINER_NAME"
    exit 1
fi

