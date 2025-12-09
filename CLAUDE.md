# ECC Sheet - Project Overview

**Medical shift tracking and reporting system with comprehensive audit logging**

**Last Updated:** 2025-11-25 | **Status:** Production-ready with enhanced UX

## Recent Major Updates (2025-11-25)

### Authentication & Security
- Simplified authentication using environment variables only (USER_NAME, ADMIN_USERS)
- Removed login system - authentication handled externally
- Admin features gated by ADMIN_USERS environment variable

### Frontend Improvements
- Migrated to Vite for asset bundling (Bootstrap, Bootstrap Icons, Luxon)
- Local package management - no CDN dependencies
- 24-hour time format enforced (lang="en-GB")
- Time always rounds UP to next 15-minute increment (not to nearest)
- Prettier integration for code formatting

### User Experience Enhancements
- Reorganized navigation - "Admin" submenu includes Residents, Roles, and Audit Log
- Clickable resident names in reports to expand details
- Quick report buttons auto-submit forms
- Loading states for async operations
- Confirmation dialogs for destructive actions
- Tooltips for clickable elements and help text
- Full hour and minute editing for role cutoff times
- Required exit time validation on entry forms

## Quick Start

```bash
# Backend setup (Python with UV)
source .venv/bin/activate
uv sync

# Frontend setup (Node packages)
bun install

# Build frontend assets
bun run build

# Apply database migrations
uv run flask --app backend.app db upgrade

# Run application
uv run python -m backend.app
```

Application available at: `http://localhost:5000` (or port configured in environment)

## Tech Stack

### Backend

- **Python 3.11+** with Flask 3.0
- **SQLite** - File-based database with migration support
- **SQLAlchemy** - ORM with relationship management
- **Flask-Migrate (Alembic)** - Database version control
- **Flask-WTF** - Form validation with CSRF protection
- **Requests** - HTTP client for Amion API integration

### Frontend

- **Jinja2** - Server-side templates with 24-hour time format (lang="en-GB")
- **Vanilla JavaScript** - ES6+ with Luxon for timezone handling
- **Bootstrap 5.3.8** - UI framework (bundled locally via Vite)
- **Bootstrap Icons 1.13.1** - Icon library (bundled locally)
- **Luxon 3.7.2** - DateTime library with timezone support (America/New_York)
- **Vite 7.2.4** - Build tool for asset bundling
- **Prettier 3.6.2** - Code formatter for JS, CSS, and HTML

### Build Tools

- **Bun** - JavaScript runtime and package manager
- **Vite** - Frontend build tool and bundler
- **Prettier** - Code formatting
- **Stylelint** - CSS linting

## Project Structure

```
ecc-sheet/
├── backend/                 # Backend Python code
│   ├── app.py              # Main Flask application & routes
│   ├── models.py           # SQLAlchemy database models
│   ├── audit.py            # Audit logging utilities
│   ├── auth.py             # Environment-based authorization
│   ├── config.py           # Configuration from environment
│   └── __init__.py
│
├── frontend/                # Frontend templates and static files
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html       # Base template with navigation
│   │   ├── index.html      # Daily sheet with inline editing
│   │   ├── residents.html  # Resident management
│   │   ├── roles.html      # Role configuration
│   │   ├── reports.html    # Report generation
│   │   ├── report_results.html  # Report display with CSV export
│   │   └── audit.html      # Audit log viewer
│   └── static/
│       ├── dist/           # Vite build output (vendor bundles)
│       ├── js/             # Source JavaScript files
│       │   ├── vendor.js   # Vendor bundle entry point
│       │   ├── script.js   # Application JavaScript
│       │   └── luxon-utils.js  # Luxon timezone utilities
│       └── css/
│           └── style.css   # Custom CSS overrides
│
├── migrations/              # Database migration files
│   ├── versions/           # Migration version files
│   ├── env.py
│   └── script.py.mako
│
├── instance/                # Instance-specific files
│   └── ecc_sheet.db        # SQLite database (git-ignored)
│
├── docs/                    # Documentation
│   ├── DATABASE_MIGRATIONS.md  # Migration workflow guide
│   └── archive/            # Archived documentation
│
├── node_modules/            # Node.js dependencies (git-ignored)
├── package.json            # Node.js dependencies and scripts
├── vite.config.js          # Vite bundler configuration
├── .prettierrc.json        # Prettier configuration
├── .prettierignore         # Prettier ignore patterns
├── pyproject.toml          # Python dependencies and configuration
└── CLAUDE.md               # This file
```

## Database Schema

### Core Tables

**residents**
- `id` (PK) - Auto-incrementing ID
- `name` - Resident name
- `epic_id` - Unique EPIC identifier (auto-populated from Amion imports)
- `active` - Boolean for active status
- `created_at` - Timestamp

**roles**
- `id` (PK) - Auto-incrementing ID
- `name` - Role name (ECC 1, ECA 1, etc.)
- `cutoff_hour` - Overtime cutoff hour (0-23, default 17)
- `cutoff_minute` - Overtime cutoff minute (0-59, default 30)
- `display_order` - Display ordering

**time_entries**
- `id` (PK) - Auto-incrementing ID
- `date` - Entry date (indexed)
- `resident_id` (FK) - References residents.id
- `role_id` (FK) - References roles.id
- `stop_time` - Stop time
- `exit_time` - Exit time for overtime calculation (required, rounds UP to next 15 min)
- `airway_assist` - Boolean flag
- `emergency` - Boolean flag
- `dinner_break` - Boolean flag
- `paper_record` - Boolean flag
- `locked` - Entry lock status
- `submitted` - Submission status
- `submitted_at` - Submission timestamp
- `created_at` / `updated_at` - Timestamps

**daily_sheets**
- `id` (PK) - Auto-incrementing ID
- `date` - Sheet date (unique, indexed)
- `locked` - Lock status
- `locked_by` - User who locked the sheet (from USER_NAME env)
- `locked_at` - Lock timestamp
- `submitted` - Submission status
- `submitted_at` - Submission timestamp
- `notes` - Sheet notes
- `created_at` / `updated_at` - Timestamps

**audit_logs**
- `id` (PK) - Auto-incrementing ID
- `timestamp` (indexed) - When the action occurred
- `user` - User who performed the action (from USER_NAME env)
- `action` - Action type (CREATE, UPDATE, DELETE, LOCK, UNLOCK, IMPORT)
- `entity_type` - Entity type (TimeEntry, DailySheet, Resident, Schedule)
- `entity_id` - ID of affected entity
- `details` - JSON string with change details
- `ip_address` - Client IP address

### Database Migrations

See `docs/DATABASE_MIGRATIONS.md` for complete migration workflow.

**Key Commands:**
```bash
# Create new migration after model changes
uv run flask --app backend.app db migrate -m "description"

# Apply migrations
uv run flask --app backend.app db upgrade

# Check current revision
uv run flask --app backend.app db current

# View migration history
uv run flask --app backend.app db history
```

## Key Features

### 1. Daily Sheet Management (frontend/templates/index.html)

**Inline Time Editing:**
- Click exit time to edit (tooltip: "Click to edit time")
- Time inputs display in 24-hour format (enforced with lang="en-GB")
- Time values always round UP to next 15-minute increment
- Save/Cancel buttons per entry
- "Edit All" mode enables all entries simultaneously
- "Save All" submits all changes asynchronously with loading spinner

**Sheet Operations:**
- Add new time entries (exit time required)
- Navigate between dates (Previous/Today/Next)
- Lock/unlock sheets (tracks who and when)
- Import schedule from Amion
- View lock status with user and timestamp

**Overtime Calculation:**
- Automatic calculation based on role cutoff times (hour and minute)
- Overnight shift support (exit times before cutoff treated as next day)
- Configurable cutoff per role (default 17:30)

### 2. Schedule Import from Amion (backend/app.py:346)

**Route:** `POST /import_schedule/<date_str>`

**Process:**
1. Fetches CSV from Amion API: `http://www.amion.com/cgi-bin/ocs?Lo=upennane&Rpt=619&Day={day}&Month={month}`
2. Parses CSV data for resident assignments
3. Extracts EPIC IDs (format: "EPICID:R103348" → "R103348")
4. Finds or creates residents by EPIC ID
5. Creates time entries for relevant roles only
6. Logs import action with entry count to audit trail

**Supported Roles:**
- ECC 1, 2, 3, 4, 5
- ECA 1, 2
- Late Late 1, 2
- PPMC
- Huld
- EP/HUP roles (13, 12, H13, H14)

### 3. Resident Management (frontend/templates/residents.html)

**Features:**
- Add residents (EPIC ID auto-populated from imports)
- Activate/deactivate residents with confirmation
- EPIC ID tooltip explains auto-population
- View creation timestamps

### 4. Role Configuration (frontend/templates/roles.html)

**Features:**
- Configure overtime cutoff times per role (hour AND minute)
- View current settings
- Set display order for role listing
- Default cutoff: 17:30 (5:30 PM)

**Pre-configured Roles:**
- ECA 1, ECA 2
- ECC 1-5
- PPMC
- Late Late 1, Late Late 2
- Huld
- EP/HUP variants

### 5. Reporting (frontend/templates/reports.html, report_results.html)

**Quick Reports (Auto-submit):**
- Last 7 Days - One click to generate report
- Last 30 Days - One click to generate report
- Last 90 Days - One click to generate report

**Custom Reports:**
- Select date range manually
- Filter by specific resident or all residents
- View total overtime hours per resident

**Report Display:**
- Click resident name to expand/collapse details
- Clean two-column layout (no "View Details" button)
- Export to CSV
- Print-friendly formatting

**CSV Export:**
- Columns: Date, Resident, Role, Exit Time, Overtime Hours
- Filename includes date range: `overtime_report_YYYY-MM-DD_to_YYYY-MM-DD.csv`
- Preserves filter selections

### 6. Audit Trail (frontend/templates/audit.html, backend/audit.py)

**Tracked Actions:**
- CREATE - New time entries, residents, roles
- UPDATE - Modifications to entries with change details
- DELETE - Entry deletions (logged before deletion)
- LOCK/UNLOCK - Sheet lock status changes
- IMPORT - Schedule imports with entry counts

**Audit Information:**
- Timestamp (indexed for performance)
- User performing action (from USER_NAME env var)
- IP address of client
- Entity type and ID
- JSON details with specific changes

**Filtering:**
- By entity type (TimeEntry, DailySheet, Resident, Schedule)
- By action type (CREATE, UPDATE, DELETE, LOCK, UNLOCK, IMPORT)
- By result limit (50, 100, 500, 1000)

**Access:** Admin menu → Audit Log

## Authentication & Authorization

### Environment-Based Auth

**No Login System:**
- Authentication handled externally (SSO, reverse proxy, etc.)
- User identity passed via `USER_NAME` environment variable

**Admin Access:**
- `ADMIN_USERS` environment variable contains comma-separated list
- Example: `ADMIN_USERS=Admin,John Doe,Jane Smith`
- Admin features hidden from non-admin users

**Protected Routes:**
- Residents management (admin only)
- Roles configuration (admin only)
- Audit log (admin only)

### Configuration

Environment variables in `.env`:
```env
# Required
SECRET_KEY=<generate-strong-key>
DATABASE_URL=sqlite:///ecc_sheet.db
USER_NAME=Admin

# Admin access (comma-separated)
ADMIN_USERS=Admin,John Doe

# Optional
TIMEZONE=America/New_York
```

## Navigation Structure

```
- Daily Sheet (/)
- Admin ▼ (admin only)
  ├── Residents
  ├── Roles
  └── Audit Log (separated by divider)
- Reports
- [Current User Name]
```

## Frontend Development

### Building Assets

```bash
# Install dependencies
bun install

# Build for production
bun run build

# Watch mode for development
bun run dev
```

### Code Formatting

```bash
# Format all code
bun run format

# Format specific types
bun run format:js      # JavaScript only
bun run format:css     # CSS only
bun run format:html    # HTML templates only

# Check formatting without modifying
bun run format:check
```

### Vite Configuration

**Bundle Output:**
- `frontend/static/dist/vendor.css` - Bootstrap + Bootstrap Icons CSS
- `frontend/static/dist/vendor.js` - Bootstrap JS + Luxon
- `frontend/static/dist/*.woff2` - Icon fonts

**Entry Point:** `frontend/static/js/vendor.js`

### Time Handling

**Luxon Utilities** (`frontend/static/js/luxon-utils.js`):
- `roundToQuarterHour(time)` - Rounds UP to next 15-min increment
- `getTodayPhilly()` - Current date in America/New_York timezone
- `formatDate(date)` - Format dates consistently
- `formatTime(time)` - Format times in 24-hour format
- `getDateRange(period)` - Calculate date ranges for quick reports

**Time Format:**
- All time inputs use `type="time"` with `step="900"` (15 minutes)
- HTML lang="en-GB" enforces 24-hour time picker display
- Time values always round UP to next 15-minute increment
- Display format: HH:MM (24-hour)

## API Endpoints

### Data Endpoints (GET)

**`/api/residents/active`**
- Returns list of active residents
- Format: `[{"id": 1, "name": "John Doe"}, ...]`

**`/api/roles`**
- Returns list of all roles
- Format: `[{"id": 1, "name": "ECC 1", "cutoff_hour": 17, "cutoff_minute": 30}, ...]`

### Form Endpoints (POST)

**Daily Sheet Operations:**
- `/add_entry` - Add new time entry (logs CREATE)
- `/update_entry/<entry_id>` - Update time entry (logs UPDATE with changes)
- `/delete_entry/<entry_id>` - Delete time entry (logs DELETE, with confirmation)
- `/lock_sheet/<date_str>` - Toggle sheet lock (logs LOCK/UNLOCK)
- `/import_schedule/<date_str>` - Import from Amion (logs IMPORT, with confirmation)

**Resident Management:**
- `/add_resident` - Add new resident (logs CREATE)
- `/toggle_resident/<resident_id>` - Toggle active status (logs UPDATE, with confirmation)

**Role Management:**
- `/update_role/<role_id>` - Update role cutoff time (logs UPDATE)

**Reporting:**
- `/reports` - Report generation form (GET)
- `/generate_report` - Generate report (POST)
- `/export_report_csv` - Export report as CSV (POST)

**Audit:**
- `/audit` - View audit trail (GET with optional filters)

All POST endpoints require CSRF token.

## Audit Logging Implementation

### Backend Integration (backend/audit.py)

**Helper Functions:**
```python
# Log create action
log_create("TimeEntry", entry.id, {
    "date": "2025-11-25",
    "resident": "John Doe",
    "role": "ECC 1"
})

# Log update with changes
log_update("TimeEntry", entry.id, changes={
    "exit_time": {"old": "18:00", "new": "19:30"}
})

# Log delete
log_delete("TimeEntry", entry.id, {
    "resident": "John Doe",
    "date": "2025-11-25"
})

# Log lock/unlock
log_lock("2025-11-25", locked=True)

# Log import
log_import("2025-11-25", entries_count=15)
```

**Automatic Data Capture:**
- User from `USER_NAME` config or parameter
- IP address from request headers (X-Forwarded-For, X-Real-IP, or remote_addr)
- Timestamp (UTC)
- Details serialized to JSON

## Security

### Current Protections

- **CSRF Protection** - Flask-WTF active on all forms
- **SQL Injection** - SQLAlchemy ORM with parameterized queries
- **XSS Protection** - Jinja2 auto-escaping
- **Input Validation** - WTForms validation with required fields
- **Audit Trail** - Complete change tracking with IP addresses
- **Data Backups** - Database file can be backed up via file copy
- **Confirmation Dialogs** - For all destructive actions
- **Time Validation** - Always rounds up (favors resident)

### Production Recommendations

Before internet deployment:
- Implement proper authentication (external SSO recommended)
- Add rate limiting (Flask-Limiter)
- Enable HTTPS/SSL
- Use production WSGI server (gunicorn, uwsgi)
- Conduct security audit
- Implement session management
- Review ADMIN_USERS configuration
- Set up automated database backups
- Configure proper logging and monitoring

## Development Workflow

### Initial Setup

```bash
# Create virtual environment and install Python dependencies
uv venv
source .venv/bin/activate
uv sync

# Install Node.js dependencies
bun install

# Build frontend assets
bun run build

# Apply migrations
uv run flask --app backend.app db upgrade

# Run application
uv run python -m backend.app
```

### Making Schema Changes

```bash
# 1. Modify models in backend/models.py
# 2. Generate migration
uv run flask --app backend.app db migrate -m "Add new field"
# 3. Review generated migration in migrations/versions/
# 4. Apply migration
uv run flask --app backend.app db upgrade
# 5. Test changes
```

### Frontend Development

```bash
# Watch mode - rebuilds on file changes
bun run dev

# Format code before committing
bun run format

# Check formatting
bun run format:check

# Lint CSS
bun run lint:css
```

### Code Quality

**Automated Formatting:**
- JavaScript: Prettier with 4-space tabs
- CSS: Prettier with 4-space tabs
- HTML: Prettier with 4-space tabs, 120 char line width
- Configuration: `.prettierrc.json`

**Linting:**
- CSS: Stylelint with standard config
- Run: `bun run lint:css`

## Troubleshooting

### Migration Issues

**Problem:** "Target database is not up to date"
```bash
# Check current revision
uv run flask --app backend.app db current

# View pending migrations
uv run flask --app backend.app db heads

# Apply pending migrations
uv run flask --app backend.app db upgrade
```

**Problem:** Migration conflicts
```bash
# View migration history
uv run flask --app backend.app db history

# Downgrade if needed
uv run flask --app backend.app db downgrade <revision>
```

### Frontend Build Issues

**Problem:** Vite build fails
```bash
# Clear node_modules and reinstall
rm -rf node_modules
bun install
bun run build
```

**Problem:** Icons not displaying
```bash
# Rebuild assets to regenerate font paths
bun run build
# Verify vendor.css contains relative paths: ./bootstrap-icons.woff2
grep "bootstrap-icons" frontend/static/dist/vendor.css
```

### Database Issues

**Problem:** Database locked
- SQLite locks on writes - usually resolves on retry
- Check for long-running transactions
- Restart application if persistent

**Problem:** Missing audit logs
- Verify audit logging is not disabled in code
- Check USER_NAME config is set
- Review error logs for audit logging failures

### Import Issues

**Problem:** Schedule import fails
- Verify Amion URL is accessible
- Check CSV format hasn't changed
- Review import logs in audit trail
- Ensure residents have EPIC IDs

## File References

### Core Application Files

**backend/app.py** - Main application
- Authentication removed, uses env vars
- All routes with audit logging
- Admin-protected routes use @admin_required decorator

**backend/auth.py** - Authorization utilities
- `get_current_user()` - Returns USER_NAME from env
- `is_admin()` - Checks ADMIN_USERS list
- `@admin_required` - Route decorator for admin features

**backend/models.py** - Database models
- Resident model with epic_id
- Role model with cutoff_hour and cutoff_minute
- TimeEntry model with overtime calculation
- DailySheet model with lock tracking
- AuditLog model

**backend/audit.py** - Audit utilities
- Main log_action function
- Helper functions for each action type
- Automatic IP address and user capture

**frontend/templates/base.html** - Base template
- lang="en-GB" for 24-hour time format
- Admin submenu structure
- Bundled vendor CSS/JS from Vite

**frontend/templates/index.html** - Daily sheet UI
- Inline editing with tooltips
- Edit All / Save All with loading states
- Required exit time field
- Time rounding message

**frontend/templates/residents.html** - Resident management
- EPIC ID tooltip
- Confirmation dialogs

**frontend/templates/roles.html** - Role configuration
- Hour and minute cutoff editing
- Current setting display

**frontend/templates/reports.html** - Report generation
- Quick report buttons (auto-submit)
- Custom date range selection

**frontend/templates/report_results.html** - Report display
- Clickable resident names for details
- CSV export functionality

**frontend/templates/audit.html** - Audit viewer
- Filtering interface
- Audit trail table

**frontend/static/js/vendor.js** - Vite entry point
- Imports Bootstrap CSS/JS
- Imports Bootstrap Icons
- Imports Luxon and makes it global

**frontend/static/js/luxon-utils.js** - DateTime utilities
- roundToQuarterHour - Always rounds UP
- Timezone-aware date operations
- Philadelphia timezone (America/New_York)

**vite.config.js** - Vite configuration
- Bundles to frontend/static/dist
- Relative paths for assets (base: './')

**.prettierrc.json** - Prettier configuration
- 4-space indentation
- 120 character line width
- HTML/CSS/JS formatting rules

## License

MIT - Free to use and modify
