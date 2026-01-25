#!/bin/bash
#
# Database Backup Script for ECC Sheet
# Creates daily backups of the SQLite database
#
# Usage: ./scripts/backup_database.sh
# Cron: 0 2 * * * /path/to/scripts/backup_database.sh

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${PROJECT_ROOT}/instance/ecc_sheet.db"
BACKUP_DIR="${PROJECT_ROOT}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/ecc_sheet_${TIMESTAMP}.db"
LOG_FILE="${BACKUP_DIR}/backup.log"
RETENTION_DAYS=30

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    log "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Create backup
log "Starting backup..."
if cp "$DB_PATH" "$BACKUP_FILE"; then
    log "Database backed up to: $BACKUP_FILE"

    # Compress backup
    if gzip "$BACKUP_FILE"; then
        log "Backup compressed: ${BACKUP_FILE}.gz"
        BACKUP_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
        log "Backup size: $BACKUP_SIZE"
    else
        log "WARNING: Compression failed, keeping uncompressed backup"
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log "Backup size: $BACKUP_SIZE"
    fi
else
    log "ERROR: Backup failed"
    exit 1
fi

# Delete old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "ecc_sheet_*.db.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
if [ "$DELETED_COUNT" -gt 0 ]; then
    log "Deleted $DELETED_COUNT old backup(s)"
else
    log "No old backups to delete"
fi

# Summary
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "ecc_sheet_*.db.gz" | wc -l)
log "Backup complete. Total backups: $BACKUP_COUNT"

exit 0
