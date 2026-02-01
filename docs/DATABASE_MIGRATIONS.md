# Database Migrations Guide

This project uses Flask-Migrate (Alembic) for database schema versioning and
migrations.

## Overview

Database migrations allow you to:

- Track changes to your database schema over time
- Apply changes consistently across environments
- Rollback changes if needed
- Collaborate with others without conflicts

## Migration Commands

All commands use the Flask CLI:

### View Current Migration Status

```bash
uv run flask --app backend.app db current
```

### View Migration History

```bash
uv run flask --app backend.app db history
```

### Create a New Migration

After changing models in `backend/models.py`, generate a migration:

```bash
uv run flask --app backend.app db migrate -m "Description of changes"
```

Example:

```bash
uv run flask --app backend.app db migrate -m "Add user_role field to residents"
```

### Apply Migrations

Apply all pending migrations:

```bash
uv run flask --app backend.app db upgrade
```

Apply to a specific version:

```bash
uv run flask --app backend.app db upgrade <revision>
```

### Rollback Migrations

Rollback the last migration:

```bash
uv run flask --app backend.app db downgrade
```

Rollback to a specific version:

```bash
uv run flask --app backend.app db downgrade <revision>
```

## Workflow for Schema Changes

1. **Edit Models**: Make changes to `backend/models.py`

2. **Generate Migration**:

   ```bash
   uv run flask --app backend.app db migrate -m "Your change description"
   ```

3. **Review Migration**: Check the generated file in `migrations/versions/`

   - Ensure the upgrade/downgrade logic is correct
   - Add any custom data migrations if needed

4. **Apply Migration**:

   ```bash
   uv run flask --app backend.app db upgrade
   ```

5. **Commit**: Add both the model changes and migration file to git:
   ```bash
   git add backend/models.py migrations/versions/*.py
   git commit -m "Add user_role field to residents"
   ```

## Migration Files

Migration files are stored in: `migrations/versions/`

Each migration file contains:

- `revision`: Unique identifier for this migration
- `down_revision`: Previous migration in the chain
- `upgrade()`: SQL commands to apply the migration
- `downgrade()`: SQL commands to reverse the migration

## Current Schema Version

The current schema includes:

### Residents Table

- `id`: Primary key
- `name`: Resident name
- `epic_id`: Unique EPIC ID from Amion (nullable, unique)
- `active`: Boolean flag
- `created_at`: Timestamp

### Roles Table

- `id`: Primary key
- `name`: Role name (unique)
- `cutoff_hour`: Overtime cutoff hour
- `cutoff_minute`: Overtime cutoff minute
- `display_order`: Sort order

### TimeEntries Table

- `id`: Primary key
- `date`: Entry date
- `resident_id`: Foreign key to residents
- `role_id`: Foreign key to roles
- `exit_time`: Exit time
- `locked`, `submitted`: Status flags
- `created_at`, `updated_at`: Timestamps

### DailySheets Table

- `id`: Primary key
- `date`: Sheet date (unique)
- `locked`: Lock status
- `locked_by`: Who locked the sheet (nullable)
- `locked_at`: When the sheet was locked (nullable)
- `submitted`: Submission status
- `submitted_at`: Submission timestamp
- `notes`: Text field
- `created_at`, `updated_at`: Timestamps

## Troubleshooting

### "Can't locate revision"

This means the database's migration version is out of sync. To reset:

```bash
uv run flask --app backend.app db stamp head
```

### "Duplicate column" errors

The column already exists in the database. Either:

- Skip this migration: `uv run flask --app backend.app db stamp <revision>`
- Or manually remove the column and rerun the migration

### Starting Fresh

To reset all migrations:

```bash
# Backup your data first!
rm instance/ecc_sheet.db
uv run flask --app backend.app db upgrade
```

## Best Practices

1. **Always review** generated migrations before applying
2. **Test migrations** in development before production
3. **Backup database** before applying migrations in production
4. **One change per migration** for easier rollbacks
5. **Descriptive messages** help future you understand changes
6. **Commit migrations** with the code that requires them

## Example: Adding a New Field

Let's say you want to add an `email` field to the Resident model:

1. Edit `backend/models.py`:

   ```python
   class Resident(db.Model):
       # ... existing fields ...
       email = db.Column(db.String(120), nullable=True)
   ```

2. Generate migration:

   ```bash
   uv run flask --app backend.app db migrate -m "Add email field to residents"
   ```

3. Review the generated file in `migrations/versions/`

4. Apply the migration:

   ```bash
   uv run flask --app backend.app db upgrade
   ```

5. Commit both files:
   ```bash
   git add backend/models.py migrations/versions/*_add_email_field_to_residents.py
   git commit -m "Add email field to residents table"
   ```

## Production Deployment

When deploying to production:

1. **Backup the database**

   ```bash
   cp instance/ecc_sheet.db instance/ecc_sheet.db.backup
   ```

2. **Pull latest code**

   ```bash
   git pull origin main
   ```

3. **Apply migrations**

   ```bash
   uv run flask --app backend.app db upgrade
   ```

4. **Restart the application**

## Configuration

Migration settings are in `migrations/alembic.ini`. The connection string is
automatically configured from your Flask app.

You can set the database URL via environment variable:

```bash
DATABASE_URL="sqlite:///production.db"
```
