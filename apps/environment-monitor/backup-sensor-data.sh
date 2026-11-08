#!/bin/bash
# Sensor Data Backup Script with Email Notifications

VOLUME_NAME="environment-monitor_sensor_data"
BACKUP_DIR="/home/leo/sensor-backups"
LOG_FILE="/home/leo/sensor-backups/backup.log"
EMAIL_TO="leo.defig@gmail.com"
DATE=$(date +%Y%m%d_%H%M%S)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
HOSTNAME=$(hostname)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Function to log messages
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

# Function to send email notification
send_email() {
    local subject="$1"
    local body="$2"
    local status="$3"
    
    # Create email content
    cat <<EOF > /tmp/backup_email.txt
To: $EMAIL_TO
From: Sensor Monitor <leo.defig@gmail.com>
Subject: $subject

$body

---
Sensor Monitoring System
Host: $HOSTNAME
Time: $TIMESTAMP
EOF

    # Send email
    if msmtp "$EMAIL_TO" < /tmp/backup_email.txt; then
        log "📧 Email notification sent to $EMAIL_TO"
    else
        log "❌ Failed to send email notification"
    fi
    
    # Clean up
    rm -f /tmp/backup_email.txt
}

log "Starting sensor data backup..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    ERROR_MSG="Docker is not running!"
    log "❌ $ERROR_MSG"
    send_email "🚨 Sensor Backup Failed - Docker Issue" "Backup failed because Docker is not running.

Please check the Docker service on $HOSTNAME.

Error: $ERROR_MSG" "FAILED"
    exit 1
fi

# Check if volume exists
if ! docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
    ERROR_MSG="Volume $VOLUME_NAME does not exist!"
    log "❌ $ERROR_MSG"
    send_email "🚨 Sensor Backup Failed - Volume Missing" "Backup failed because the sensor data volume is missing.

Volume: $VOLUME_NAME
Host: $HOSTNAME

Error: $ERROR_MSG" "FAILED"
    exit 1
fi

# Create compressed backup from named volume
log "Creating backup: sensor-data-$DATE.tar.gz"

docker run --rm \
  -v "$VOLUME_NAME:/data:ro" \
  -v "$BACKUP_DIR:/backup" \
  alpine \
  tar czf "/backup/sensor-data-$DATE.tar.gz" -C /data . >/dev/null 2>&1

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(ls -lh "$BACKUP_DIR/sensor-data-$DATE.tar.gz" | awk '{print $5}')
    log "✅ Backup created successfully: sensor-data-$DATE.tar.gz ($BACKUP_SIZE)"
    
    # Keep only last 30 backups
    cd "$BACKUP_DIR"
    DELETED=$(ls -t sensor-data-*.tar.gz 2>/dev/null | tail -n +31 | wc -l)
    ls -t sensor-data-*.tar.gz 2>/dev/null | tail -n +31 | xargs -r rm -f
    
    if [ "$DELETED" -gt 0 ]; then
        log "🧹 Cleaned up $DELETED old backup(s) (keeping last 30)"
    fi
    
    # Log current backup count
    TOTAL_BACKUPS=$(ls -1 sensor-data-*.tar.gz 2>/dev/null | wc -l)
    log "📊 Total backups: $TOTAL_BACKUPS"
    
    # Send success email
    send_email "✅ Sensor Backup Completed Successfully" "Daily sensor data backup completed successfully!

📊 Backup Details:
• File: sensor-data-$DATE.tar.gz
• Size: $BACKUP_SIZE
• Total backups: $TOTAL_BACKUPS
• Cleaned up: $DELETED old backup(s)

🖥️ System: $HOSTNAME
📅 Date: $TIMESTAMP
📁 Location: $BACKUP_DIR

Your sensor data is safely backed up and ready for recovery if needed." "SUCCESS"

else
    ERROR_MSG="Backup creation failed!"
    log "❌ $ERROR_MSG"
    send_email "🚨 Sensor Backup Failed - Creation Error" "The daily sensor backup failed during file creation.

This could indicate:
• Disk space issues
• Docker container problems  
• Volume access issues

Please investigate immediately to ensure data protection.

Host: $HOSTNAME
Time: $TIMESTAMP
Error: $ERROR_MSG" "FAILED"
    exit 1
fi

log "Backup completed successfully"
