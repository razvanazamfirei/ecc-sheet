# Production Deployment Guide

## Current State: Development Only ⚠️

**The current application is NOT production-ready and should NOT be exposed to
the internet without significant hardening.**

## Critical Issues

### 1. Database (SQLite)

**Current**: Single file database (`ecc_sheet.db`)

**Problems**:

- Not suitable for concurrent writes
- Can corrupt under load
- No built-in replication
- Limited to ~1000 requests/second

**Solution**:

```bash
# Switch to PostgreSQL
uv pip install psycopg2-binary

# Update .env
DATABASE_URL=postgresql://user:password@localhost:5432/eccsheet

# Migration
pg_dump existing_db | psql new_db
```

### 2. No Error Recovery

**Problems**:

- App crashes on unexpected errors
- No graceful degradation
- Lost requests during crashes

**Solution**:

```python
# Use the provided utils.py with error decorators
from ..utils import handle_db_error, setup_logging

# Add logging
logger = setup_logging()


# Wrap all routes
@app.route('/entries/add', methods=['POST'])
@handle_db_error
def add_entry():
# Your code here
```

### 3. Email Reliability

**Current**: Single attempt, fails silently

**Solution**: Use `enhanced_scheduler.py` which includes:

- Retry logic (3 attempts)
- Exponential backoff
- Error logging
- Graceful failure handling

### 4. No Monitoring

**Problems**:

- Don't know when app is down
- No visibility into errors
- Can't track performance

**Solutions**:

```bash
# Application monitoring
uv pip install prometheus-flask-exporter

# Error tracking
uv pip install sentry-sdk[flask]
```

```python
# In app.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0
)
```

### 5. Data Loss Risk

**No backups** means any of these cause total data loss:

- File corruption
- Disk failure
- Accidental deletion
- Ransomware

**Solution**: Automated backups (included in `enhanced_scheduler.py`)

```python
# Backups every day at 2 AM
# Keeps last 30 backups
# Stored in backups/ directory

# Test restore:
cp backups/ecc_sheet_20250121_020000.db ecc_sheet.db
```

## Production Architecture

### Recommended Setup

```
Internet
    ↓
[Load Balancer / CloudFlare]
    ↓
[Nginx (SSL, static files, rate limiting)]
    ↓
[Gunicorn (4 workers)]
    ↓
[Flask App]
    ↓
[PostgreSQL Database]
    ↓
[S3/Cloud Storage for backups]
```

### Deployment Steps

#### 1. Server Setup

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx postgresql python3.11 python3-pip

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create app user
sudo useradd -m -s /bin/bash eccapp
sudo -u eccapp -i
```

#### 2. Application Setup

```bash
cd /home/eccapp
git clone <your-repo>
cd ecc-sheet

# Setup with UV
uv venv
source .venv/bin/activate
uv pip install -e .

# Production dependencies
uv pip install gunicorn psycopg2-binary sentry-sdk
```

#### 3. Database Setup

```bash
sudo -u postgres psql

CREATE DATABASE eccsheet;
CREATE USER eccapp WITH PASSWORD 'strong-password-here';
GRANT ALL PRIVILEGES ON DATABASE eccsheet TO eccapp;
\q
```

#### 4. Environment Configuration

```bash
# /home/eccapp/ecc-sheet/.env
SECRET_KEY=<generate-with-secrets.token_hex(32)>
DATABASE_URL=postgresql://eccapp:password@localhost:5432/eccsheet
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENT=recipient@example.com
DEFAULT_CUTOFF_HOUR=8
TIMEZONE=America/New_York

# Secure it
chmod 600 .env
```

#### 5. Systemd Service

```bash
# /etc/systemd/system/eccsheet.service
[Unit]
Description=ECC Sheet Application
After=network.target postgresql.service

[Service]
Type=notify
User=eccapp
Group=eccapp
WorkingDirectory=/home/eccapp/ecc-sheet
Environment="PATH=/home/eccapp/ecc-sheet/.venv/bin"
ExecStart=/home/eccapp/ecc-sheet/.venv/bin/gunicorn \
    --workers 4 \
    --bind unix:/tmp/eccsheet.sock \
    --timeout 120 \
    --access-logfile /var/log/eccsheet/access.log \
    --error-logfile /var/log/eccsheet/error.log \
    app:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable eccsheet
sudo systemctl start eccsheet
sudo systemctl status eccsheet
```

#### 6. Nginx Configuration

```nginx
# /etc/nginx/sites-available/eccsheet
server {
    listen 80;
    server_name ecc-sheet.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ecc-sheet.example.com;

    ssl_certificate /etc/letsencrypt/live/ecc-sheet.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ecc-sheet.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 10M;

    location /static {
        alias /home/eccapp/ecc-sheet/static;
        expires 30d;
    }

    location / {
        proxy_pass http://unix:/tmp/eccsheet.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/eccsheet /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 7. SSL Certificate

```bash
# Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d ecc-sheet.example.com
```

#### 8. Automated Backups

```bash
# Cron for database backups (in addition to app backups)
# /etc/cron.daily/eccsheet-backup

#!/bin/bash
BACKUP_DIR="/backups/eccsheet"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# PostgreSQL backup
sudo -u postgres pg_dump eccsheet | gzip > $BACKUP_DIR/eccsheet_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/eccsheet_$DATE.sql.gz s3://your-bucket/backups/
```

## Monitoring & Maintenance

### Health Checks

```python
# Add to app.py
@app.route('/health')
def health():
    try:
        # Check database
        db.session.execute('SELECT 1')
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503
```

### Logging

```bash
# View logs
sudo journalctl -u eccsheet -f

# Application logs
tail -f /var/log/eccsheet/error.log
tail -f /var/log/eccsheet/access.log
```

### Performance Monitoring

```bash
# Install monitoring tools
uv pip install prometheus-flask-exporter

# In app.py
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)
```

### Database Maintenance

```bash
# Regular maintenance
sudo -u postgres psql eccsheet

-- Vacuum and analyze
VACUUM ANALYZE;

-- Check table sizes
SELECT pg_size_pretty(pg_total_relation_size('time_entries'));

-- Monitor connections
SELECT count(*) FROM pg_stat_activity;
```

## Disaster Recovery

### Backup Verification

```bash
# Test database restore monthly
pg_restore -d test_db backup.sql.gz
# Verify data integrity
# Drop test database
```

### Recovery Procedure

1. **Database Corruption**

   ```bash
   sudo systemctl stop eccsheet
   sudo -u postgres psql < /backups/latest.sql
   sudo systemctl start eccsheet
   ```

2. **Application Failure**

   ```bash
   sudo systemctl restart eccsheet
   # If that doesn't work:
   sudo systemctl stop eccsheet
   # Check logs, fix issue
   sudo systemctl start eccsheet
   ```

3. **Complete Server Failure**
   - Provision new server
   - Restore latest database backup
   - Deploy application
   - Update DNS

## Cost Estimates

### Cloud Hosting (AWS/DigitalOcean)

- **Small deployment** (<50 users):

  - EC2 t3.small or DO Droplet ($10-20/month)
  - RDS PostgreSQL db.t3.micro ($15/month)
  - Total: ~$30/month

- **Medium deployment** (<500 users):
  - EC2 t3.medium ($30/month)
  - RDS db.t3.small ($30/month)
  - Load balancer ($18/month)
  - Total: ~$80/month

### Self-Hosted

- Server hardware: One-time cost
- Power/cooling: ~$20/month
- Backup storage: ~$10/month
- Total: ~$30/month (after initial investment)

## Performance Benchmarks

With proper setup:

- **Concurrent users**: 100-500
- **Response time**: <200ms
- **Uptime**: 99.9%
- **Requests/sec**: 1000+

## Scaling Strategies

1. **Vertical** (single server):

   - Increase RAM/CPU
   - Good up to ~1000 concurrent users

2. **Horizontal** (multiple servers):
   - Load balancer + multiple app servers
   - Shared PostgreSQL database
   - Redis for session storage
   - Can handle 10,000+ users

## Final Checklist

Before going live:

- [ ] PostgreSQL database configured
- [ ] All secrets in environment variables
- [ ] HTTPS enabled with valid certificate
- [ ] Backups tested and automated
- [ ] Monitoring and alerting set up
- [ ] Error tracking (Sentry) configured
- [ ] Rate limiting enabled
- [ ] CSRF protection active
- [ ] Input validation implemented
- [ ] Security headers configured
- [ ] Firewall rules in place
- [ ] Regular security updates scheduled
- [ ] Documentation updated
- [ ] Disaster recovery plan documented
- [ ] Team trained on procedures
