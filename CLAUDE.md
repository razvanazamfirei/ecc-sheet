# ECC Sheet - Project Overview

**Medical shift tracking and reporting system with comprehensive audit logging**

**Last Updated:** 2026-01-31 | **Status:** Production-ready with 99% test
coverage

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

Application available at: `http://localhost:5000` (or port configured in
environment)

## Tech Stack

### Backend

- **Python 3.13** with Flask 3.1.2
- **SQLite** - File-based database with migration support
- **SQLAlchemy** - ORM with relationship management
- **Flask-Migrate 4.1.0 (Alembic)** - Database version control
- **Flask-WTF 1.2.2** - Form validation with CSRF protection
- **Requests 2.32.5** - HTTP client for Amion API integration
- **pytz 2025.2** - Timezone handling
- **holidays 0.89** - US federal holiday tracking
- **email-validator 2.3.0** - Email validation

### Frontend

- **Jinja2** - Server-side templates with 24-hour time format (lang="en-GB")
- **Vanilla JavaScript** - ES6+ with Luxon for timezone handling
- **Bootstrap 5.3.8** - UI framework (bundled locally via Vite)
- **Bootstrap Icons 1.13.1** - Icon library (bundled locally)
- **Luxon 3.7.2** - DateTime library with timezone support (America/New_York)
- **Vite 7.3.1** - Build tool for asset bundling
- **Prettier 3.8.1** - Code formatter for JS, CSS, HTML, and Jinja templates

### Testing

- **pytest 9.0.2** - Python testing framework
- **pytest-cov 7.0.0** - Coverage plugin
- **Vitest 30.2.0** - JavaScript testing framework

### Build Tools

- **UV** - Python package manager
- **Bun** - JavaScript runtime and package manager
- **Vite** - Frontend build tool and bundler
- **Prettier** - Code formatting
- **Stylelint 17.0.0** - CSS linting
- **Ruff** - Python linting

## Project Structure

```
ecc-sheet/
├── backend/                # Backend Python code
│   ├── app.py              # Main Flask application initialization
│   ├── init_db.py          # Database initialization
│   ├── instance_config.py  # Loader for instance settings
│   ├── instance_settings.json # Configurable role definitions and cutoffs
│   ├── models.py           # SQLAlchemy database models
│   ├── audit.py            # Audit logging utilities
│   ├── auth.py             # Environment-based authorization
│   ├── config.py           # Configuration from environment
│   ├── errors.py           # Custom exception classes
│   ├── utils.py            # Logging, backups, error handling
│   ├── holidays.py         # Holiday utilities
│   ├── report_utils.py     # Report generation and CSV export
│   ├── staff_import.py     # Amion staff list parsing
│   ├── __init__.py
│   └── routes/             # Route blueprints (modular organization)
│       ├── __init__.py
│       ├── _registry.py    # Blueprint registration
│       ├── api.py          # API endpoints
│       ├── entries.py      # Time entry CRUD
│       ├── sheets.py       # Daily sheet operations
│       ├── schedule.py     # Amion schedule import
│       ├── residents.py    # Resident management
│       ├── roles.py        # Role configuration
│       ├── reports.py      # Report generation
│       ├── holidays.py     # Holiday management
│       └── audit.py        # Audit log viewer
│
├── frontend/                # Frontend templates and static files
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html       # Base template with navigation
│   │   ├── index.html      # Daily sheet with inline editing
│   │   ├── residents.html  # Resident management
│   │   ├── roles.html      # Role configuration
│   │   ├── reports.html    # Report generation
│   │   ├── report_results.html  # Report display with CSV export
│   │   ├── audit.html      # Audit log viewer
│   │   ├── holidays.html   # Holiday management
│   │   └── import_warning.html  # Schedule import confirmation
│   └── static/
│       ├── dist/           # Vite build output (vendor bundles)
│       ├── js/             # Source JavaScript files
│       │   ├── vendor.js   # Vendor bundle entry point
│       │   ├── script.js   # Main application logic
│       │   ├── daily-sheet.js   # Daily sheet UI interactions
│       │   ├── reports.js  # Report page logic
│       │   ├── luxon-utils.js   # Luxon timezone utilities
│       │   └── __tests__/  # Vitest test suites
│       │       ├── script.test.js
│       │       ├── daily-sheet.test.js
│       │       ├── luxon-utils.test.js
│       │       └── reports.test.js
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
├── tests/                   # Python test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── test_models.py
│   ├── test_models_extended.py
│   ├── test_audit.py
│   ├── test_auth.py
│   ├── test_entries.py
│   ├── test_schedule.py
│   ├── test_residents_routes.py
│   ├── test_roles_routes.py
│   ├── test_reports_routes.py
│   ├── test_holidays_routes.py
│   ├── test_api_routes.py
│   └── ... (additional test modules)
│
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md     # System architecture reference
│   └── README.md           # Documentation overview
│
├── scripts/                 # Utility scripts
│   └── logs/
│
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI/CD pipeline
│
├── node_modules/            # Node.js dependencies (git-ignored)
├── .venv/                   # Python virtual environment (git-ignored)
├── logs/                    # Application logs (git-ignored)
├── coverage/                # Test coverage reports (git-ignored)
│
├── package.json            # Node.js dependencies and scripts
├── bun.lock                # Bun lock file
├── vite.config.js          # Vite bundler configuration
├── vitest.config.js        # Vitest configuration
├── pyproject.toml          # Python dependencies and configuration
├── uv.lock                 # Python dependency lock file
├── pytest.ini              # Pytest configuration
├── prettier.config.js      # Prettier configuration
├── .prettierignore         # Prettier ignore patterns
├── stylelint.config.js     # Stylelint configuration
├── ruff.toml               # Ruff linter configuration
├── mise.toml               # Tool version management
├── codecov.yml             # Codecov configuration
└── CLAUDE.md               # This file
```

## Database Schema

### Core Tables

**residents**

- `id` (PK) - Auto-incrementing ID
- `name` - Resident name
- `epic_id` - Unique EPIC identifier (auto-populated from Amion imports)
- `class_year` - Graduation year (from staff import)
- `email` - Email address (from staff import)
- `phone` - Phone number (from staff import)
- `abbreviation` - Name abbreviation (from staff import)
- `backup_id` - Reference to backup resident (for backup roles)
- `active` - Boolean for active status
- `created_at` - Timestamp

**roles**

- `id` (PK) - Auto-incrementing ID
- `name` - Role name (ECC 1, ECA 1, etc.)
- `cutoff_hour` - Overtime cutoff hour (0-23, default 17)
- `cutoff_minute` - Overtime cutoff minute (0-59, default 30)
- `display_order` - Display ordering
- `is_backup` - Boolean indicating if this is a backup role

**time_entries**

- `id` (PK) - Auto-incrementing ID
- `date` - Entry date (indexed)
- `resident_id` (FK) - References residents.id
- `role_id` (FK) - References roles.id
- `start_time` - Start time (for backup roles)
- `stop_time` - Stop time
- `exit_time` - Exit time for overtime calculation (required, rounds UP to next
  15 min)
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

**holidays**

- `id` (PK) - Auto-incrementing ID
- `date` - Holiday date
- `name` - Holiday name
- `is_recurring` - Boolean for yearly recurrence
- Includes US federal holidays by default

## Key Features

### 1. Daily Sheet Management (frontend/templates/index.html)

**Inline Time Editing:**

- Click exit time to edit (tooltip: "Click to edit time")
- Time inputs display in 24-hour format (enforced with lang="en-GB")
- Time values always round UP to the next 5-minute increment
- Save/Cancel buttons per entry
- "Edit All" mode enables all entries simultaneously
- "Save All" submits all changes asynchronously with loading spinner

**Sheet Operations:**

- Add new time entries (exit time required)
- Navigate between dates (Previous/Today/Next)
- Lock/unlock sheets (tracks who and when)
- Import schedule from Amion
- View lock status with user and timestamp

**Copy to Clipboard (Locked Sheets Only):**

- Generates HTML table suitable for email
- Includes: Role, Name, Start Time (if weekend/holiday), Overtime
- Omits entries without exit times
- Includes introductory message with date
- Copies to clipboard in HTML format for rich email clients
- Button disabled with tooltip until sheet is locked

**Print for Signing (Locked Sheets Only):**

- Opens print-friendly view
- Minimally formatted for clean printing
- Includes signature lines for Attending and First Call
- Hides UI elements (buttons, navigation, alerts)
- Button disabled with tooltip until sheet is locked

**Backup Role Support:**

- Special roles with start and exit times
- Backup resident assignment
- Separate overtime calculation logic

**Overtime Calculation:**

- Automatic calculation based on role cutoff times (hour and minute)
- Overnight shift support (exit times before cutoff treated as next day)
- Configurable cutoff per role (default 17:30)
- Holiday awareness for overtime exceptions

### 2. Schedule Import from Amion (backend/routes/schedule.py)

**Route:** `POST /schedule/<date_str>/import`

**Process:**

1. Fetches CSV from Amion API:
   `http://www.amion.com/cgi-bin/ocs?Lo={AMION_SCHEDULE_CODE}&Rpt=619&Day={day}&Month={month}`
   (schedule code from config)
2. Parses CSV data for resident assignments
3. Extracts EPIC IDs (format: `EPICID:R103348` -> `R103348`)
4. Finds or creates residents by EPIC ID
5. Creates time entries for relevant roles only
6. Logs import action with entry count to audit trail

**Supported Roles:**

- ECC 1, 2, 3, 4, 5
- ECA 1, 2
- Late Late 1, 2
- PPMC
- Backup roles (with special handling)

**Conflict Detection:**

- Pre-import warning for existing entries
- Distinguishes data loss vs harmless duplicates
- Option to skip entries with exit times
- Confirmation dialog for overwrites

### 3. Staff Import from Amion (backend/staff_import.py)

**Route:** `POST /residents/import_staff`

**Process:**

1. Fetches staff list from Amion API (Report 706)
2. Parses resident information: name, EPIC ID, class year, email, phone
3. Creates or updates resident records
4. Maintains data consistency with existing records

**Data Captured:**

- Full name and abbreviation
- EPIC ID for matching
- Class year for organization
- Email for communications
- Phone number for contact

### 4. Holiday Management (frontend/templates/holidays.html)

**Features:**

- View US federal holidays (automatic)
- Add custom holidays
- Mark holidays as recurring (yearly)
- Delete custom holidays
- Holiday-aware overtime calculations

**Federal Holidays Included:**

- New Year's Day, MLK Day, Presidents Day, Memorial Day
- Independence Day, Labor Day, Columbus Day
- Veterans Day, Thanksgiving, Christmas Day

### 5. Resident Management (frontend/templates/residents.html)

**Features:**

- Add residents (EPIC ID auto-populated from imports)
- Import staff from Amion
- Activate/deactivate residents with confirmation
- View class year, email, phone information
- EPIC ID tooltip explains auto-population
- View creation timestamps

### 6. Role Configuration (frontend/templates/roles.html)

**Features:**

- Configure overtime cutoff times per role (hour AND minute)
- Mark roles as backup roles
- View current settings
- Set display order for role listing
- Default cutoff: 17:30 (5:30 PM)

**Pre-configured Roles:**

- ECA 1, ECA 2
- ECC 1-5
- PPMC
- Late Late 1, Late Late 2
- Backup roles

### 7. Reporting (frontend/templates/reports.html, report_results.html)

**Quick Reports (Auto-submit):**

- Last 7 Days - One click to generate report
- Last 30 Days - One click to generate report
- Last 90 Days - One click to generate report

**Custom Reports:**

- Select date range manually
- Filter by specific resident or all residents
- View total overtime hours per resident
- Holiday-aware calculations

**Report Display:**

- Click resident name to expand/collapse details
- Clean two-column layout
- Export-only workflow: detailed CSV, billing CSV, or payroll XLSX
- Print-friendly formatting

**Export Types:**

- Detailed CSV: Date, Resident, Role, Exit Time, Overtime Hours
- Billing CSV: aggregated billing/payroll-friendly resident totals
- Payroll XLSX: Lawson/UPHS-formatted workbook for payroll upload
- Export filenames include the selected date range
- Export requests reuse the same form filters and resident selection

### 8. Audit Trail (frontend/templates/audit.html, backend/audit.py)

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

**Access:** Admin menu -> Audit Log

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
- Holiday management (admin only)
- Payroll settings (payroll admin only)

### Configuration

Environment variables in `.env`:

```env
# Required
SECRET_KEY=<generate-strong-key>
DATABASE_URL=sqlite:///ecc_sheet.db
USER_NAME=Admin

# Admin access (comma-separated)
ADMIN_USERS=Admin,John Doe

# Amion Integration (for schedule/staff imports)
AMION_SCHEDULE_CODE=your-schedule-code-here

# Optional
TIMEZONE=America/New_York
PORT=5000
```

## Navigation Structure

```
- Daily Sheet (/)
- Admin ▼ (admin only)
  ├── Residents
  ├── Roles
  ├── Holidays
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

### Testing

```bash
# Run frontend tests
bun run test

# Run with coverage
bun run test:coverage
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

- All time inputs use `type="time"` with `step="300"` (5 minutes)
- HTML lang="en-GB" enforces 24-hour time picker display
- Time values always round UP to next 5-minute increment
- Display format: HH:MM (24-hour)

## API Endpoints

### Data Endpoints (GET)

**`/api/residents/active`**

- Returns list of active residents
- Format: `[{"id": 1, "name": "John Doe", ...}, ...]`

**`/api/roles`**

- Returns list of all roles
- Format:
  `[{"id": 1, "name": "ECC 1", "cutoff_hour": 17, "cutoff_minute": 30, "is_backup": false}, ...]`

### Form Endpoints (POST)

**Daily Sheet Operations:**

- `/entries/add` - Add new time entry (logs CREATE)
- `/entries/<entry_id>/update` - Update time entry (logs UPDATE with changes)
- `/entries/<entry_id>/delete` - Delete time entry (logs DELETE, with
  confirmation)
- `/sheets/<date_str>/lock` - Toggle sheet lock (logs LOCK/UNLOCK)
- `/schedule/<date_str>/import` - Import from Amion (logs IMPORT, with
  confirmation)

**Resident Management:**

- `/residents/add` - Add new resident (logs CREATE)
- `/residents/<resident_id>/toggle` - Toggle active status (logs UPDATE, with
  confirmation)
- `/residents/import_staff` - Import staff from Amion

**Role Management:**

- `/roles/<role_id>/update` - Update role cutoff time (logs UPDATE)

**Holiday Management:**

- `/holidays/add` - Add custom holiday
- `/holidays/<holiday_id>/delete` - Delete custom holiday

**Reporting:**

- `/reports` - Report generation form (GET)
- `/api/report` - Generate the on-page report view (POST)
- `/api/report/export_csv` - Export the detailed CSV report (POST)
- `/api/report/export_billing_csv` - Export the billing CSV report (POST)
- `/api/report/export_payroll_xlsx` - Export the payroll XLSX report (POST)
- Report/export form fields: `start_date`, `end_date`, optional `resident_id`

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

## Testing

### Backend Testing (pytest)

**Test Coverage: 99%**

````bash
# Run all tests
uv run pytest tests/ -v

## Security

### Current Protections

- **CSRF Protection** - Flask-WTF active on all forms
- **SQL Injection** - SQLAlchemy ORM with parameterized queries
- **XSS Protection** - Jinja2 auto-escaping
- **Input Validation** - Route-level parsing plus model validators
- **Audit Trail** - Complete change tracking with IP addresses
- **Data Backups** - Database files can be backed up via file copy
- **Confirmation Dialogs** - For all destructive actions
- **Time Validation** - Always rounds up (favors resident)
- **Email Validation** - Email addresses validated before sending
- **Error Handling** - Custom exception classes with user-friendly messages

### Production Recommendations

Before internet deployment:

- Implement proper authentication (external SSO recommended)
- Add rate limiting (Flask-Limiter)
- Enable HTTPS/SSL
- Use production WSGI server (gunicorn, uwsgi)
- Conduct security audit
- Implement session management
- Review `ADMIN_USERS` configuration
- Set up automated database backups
- Configure proper logging and monitoring
- Review email security settings

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
````

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

# Run tests
bun run test
```

### Running Tests

```bash
# Backend tests
uv run pytest tests/ -v --cov=backend

# Frontend tests
bun run test:coverage

# All tests (via CI)
# See .github/workflows/ci.yml
```

### Code Quality

**Automated Formatting:**

- JavaScript: Prettier with 4-space indentation
- CSS: Prettier with 4-space indentation
- HTML: Prettier with 4-space indentation, 120 char line width
- Jinja Templates: Prettier with jinja-template plugin
- Configuration: `prettier.config.js`

**Linting:**

- CSS: Stylelint with standard config
- Python: Ruff (configuration in `ruff.toml`)
- Run: `bun run lint:css`

## Troubleshooting

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
- Check CSV format has not changed
- Review import logs in audit trail
- Ensure residents have EPIC IDs

**Problem:** Staff import fails

- Verify Amion API access
- Check Report 706 format
- Review error logs
- Ensure network connectivity
