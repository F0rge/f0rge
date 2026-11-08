#!/bin/bash
# Sensor Data Restore Script for Named Volume

VOLUME_NAME="environment-monitor_sensor_data"
BACKUP_DIR="/home/leo/sensor-backups"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-file.tar.gz>"
    echo "Available backups:"
    ls -la "$BACKUP_DIR"/sensor-data-*.tar.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will overwrite all current sensor data!"
echo "Backup file: $BACKUP_FILE"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "🛑 Stopping containers..."
docker-compose stop

echo "📦 Restoring data from backup..."
docker run --rm \
  -v "$VOLUME_NAME:/data" \
  -v "$(dirname "$BACKUP_FILE"):/backup" \
  alpine \
  sh -c "cd /data && tar xzf /backup/$(basename "$BACKUP_FILE")"

if [ $? -eq 0 ]; then
    echo "✅ Data restored successfully!"
    echo "🚀 Starting containers..."
    docker-compose up -d
else
    echo "❌ Restore failed!"
    exit 1
fi
