# ECC Sheet - Architecture Reference

## System Overview

Medical shift tracking system with automated reporting, holiday management, and
comprehensive audit logging.

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────────────────┐
│      Flask Application          │
│  ┌─────────────────────────┐   │
│  │   Routes (Blueprints)   │   │
│  │   - CSRF Protected      │   │
│  │   - Form Validation     │   │
│  └────────┬────────────────┘   │
│           ▼                     │
│  ┌─────────────────────────┐   │
│  │   Business Logic        │   │
│  │   - Overtime calc       │   │
│  │   - Sheet locking       │   │
│  │   - Holiday mgmt        │   │
│  │   - Email reporting     │   │
│  └────────┬────────────────┘   │
│           ▼                     │
│  ┌─────────────────────────┐   │
│  │  SQLAlchemy ORM         │   │
│  └────────┬────────────────┘   │
└───────────┼─────────────────────┘
            ▼
    ┌──────────────┐
    │    SQLite    │
    │  (instance/) │
    └──────────────┘

┌─────────────────────────────────┐
│   External Services             │
│  ┌─────────────────────────┐   │
│  │  Amion API              │   │
│  │  - Schedule import      │   │
│  │  - Staff import         │   │
│  └─────────────────────────┘   │
│  ┌─────────────────────────┐   │
│  │  SMTP Server            │   │
│  │  - Email reports        │   │
│  └─────────────────────────┘   │
└─────────────────────────────────┘
```

## Directory Structure

```
ecc-sheet/
├── backend/
│   ├── app.py                  # Flask app initialization, DB setup
│   ├── models.py               # Database models (Resident, Role, TimeEntry, DailySheet, AuditLog, Holiday)
│   ├── forms.py                # WTForms (CSRF + validation)
│   ├── config.py               # Environment configuration
│   ├── auth.py                 # Authorization (@admin_required)
│   ├── audit.py                # Audit logging utilities
│   ├── errors.py               # Custom exception classes
│   ├── utils.py                # Logging, backups, timezone helpers
│   ├── email_service.py        # Email report functionality
│   ├── holidays.py             # Holiday utilities
│   ├── report_utils.py         # Report generation and CSV export
│   ├── staff_import.py         # Amion staff list parsing
│   └── routes/                 # Route blueprints (modular organization)
│       ├── __init__.py
│       ├── _registry.py        # Blueprint registration
│       ├── api.py              # API endpoints
│       ├── entries.py          # Time entry CRUD
│       ├── sheets.py           # Daily sheet operations
│       ├── schedule.py         # Amion schedule import
│       ├── residents.py        # Resident management
│       ├── roles.py            # Role configuration
│       ├── reports.py          # Report generation
│       ├── holidays.py         # Holiday management
│       └── audit.py            # Audit log viewer
│
├── frontend/
│   ├── templates/              # Jinja2 templates
│   │   ├── base.html          # Base layout
│   │   ├── index.html         # Daily sheet (main page)
│   │   ├── residents.html     # Resident management
│   │   ├── roles.html         # Role configuration
│   │   ├── reports.html       # Reporting interface
│   │   ├── report_results.html # Report display
│   │   ├── audit.html         # Audit log viewer
│   │   ├── holidays.html      # Holiday management
│   │   ├── email_report.html  # Email report template
│   │   └── import_warning.html # Schedule import confirmation
│   └── static/
│       ├── js/
│       │   ├── script.js      # Main application logic
│       │   ├── daily-sheet.js # Daily sheet UI interactions
│       │   ├── reports.js     # Report page logic
│       │   ├── luxon-utils.js # Timezone utilities
│       │   ├── vendor.js      # Vite entry point
│       │   └── __tests__/     # Jest test suites
│       ├── css/style.css      # Custom styles
│       └── dist/              # Vite build output (vendor bundles)
│
├── scripts/
│   └── logs/                   # Script execution logs
│
├── tests/                      # Pytest test suite (26 modules)
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_models_extended.py
│   ├── test_audit.py
│   ├── test_auth.py
│   ├── test_forms.py
│   ├── test_entries.py
│   ├── test_schedule.py
│   ├── test_residents_routes.py
│   ├── test_roles_routes.py
│   ├── test_reports_routes.py
│   ├── test_email_service.py
│   ├── test_holidays_routes.py
│   ├── test_api_routes.py
│   └── ... (additional test modules)
│
├── instance/
│   └── ecc_sheet.db           # SQLite database (created at runtime)
│
├── logs/                       # Application logs (auto-created)
│   └── app.log
│
└── coverage/                   # Test coverage reports (auto-created)
    ├── backend/               # Backend coverage HTML
    └── frontend/              # Frontend coverage HTML
```

## Database Schema

```sql
-- Residents
CREATE TABLE resident (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    epic_id VARCHAR(50) UNIQUE,            -- From Amion imports
    class_year INTEGER,                    -- From staff import
    email VARCHAR(120),                    -- From staff import
    phone VARCHAR(20),                     -- From staff import
    abbreviation VARCHAR(10),              -- From staff import
    backup_id INTEGER REFERENCES resident(id), -- For backup roles
    active BOOLEAN DEFAULT TRUE,
    created_at DATETIME
);

-- Roles (shift types)
CREATE TABLE role (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    cutoff_hour INTEGER DEFAULT 17,      -- Overtime threshold
    cutoff_minute INTEGER DEFAULT 30,
    display_order INTEGER,
    is_backup BOOLEAN DEFAULT FALSE      -- Special backup role flag
);

-- Time Entries
CREATE TABLE time_entry (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    resident_id INTEGER REFERENCES resident(id),
    role_id INTEGER REFERENCES role(id),
    start_time TIME,                      -- For backup roles
    stop_time TIME,
    exit_time TIME,                       -- For overtime calculation
    locked BOOLEAN DEFAULT FALSE,
    submitted BOOLEAN DEFAULT FALSE,
    submitted_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);

-- Daily Sheets
CREATE TABLE daily_sheet (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    locked BOOLEAN DEFAULT FALSE,
    locked_by VARCHAR(100),               -- Who locked the sheet
    locked_at DATETIME,                   -- When it was locked
    submitted BOOLEAN DEFAULT FALSE,
    submitted_at DATETIME,
    notes TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

-- Audit Logs
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,          -- Indexed for performance
    user VARCHAR(100) NOT NULL,           -- From USER_NAME env
    action VARCHAR(20) NOT NULL,          -- CREATE, UPDATE, DELETE, etc.
    entity_type VARCHAR(50) NOT NULL,     -- TimeEntry, DailySheet, etc.
    entity_id INTEGER,
    details TEXT,                         -- JSON string
    ip_address VARCHAR(45)                -- IPv4 or IPv6
);

-- Holidays
CREATE TABLE holiday (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE    -- Yearly recurrence
);
```

## Key Components

### 1. Flask Application (`backend/app.py`)

**Responsibilities:**

- Application initialization
- Database setup with SQLAlchemy
- Blueprint registration
- Error handler registration
- CSRF protection configuration

**Security Features:**

- `CSRFProtect` enabled globally
- Debug mode disabled in production
- Input sanitization via WTForms
- SQLAlchemy parameterized queries (SQL injection prevention)
- Jinja2 auto-escaping (XSS prevention)

**Application Factory Pattern:**

```python
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    return app
```

### 2. Route Blueprints (`backend/routes/`)

Modular route organization for better code structure:

**API Routes (`api.py`):**

- `GET /api/residents/active` - Active residents list
- `GET /api/roles` - All roles list

**Entry Routes (`entries.py`):**

- `POST /entries/add` - Add time entry
- `POST /entries/<id>/update` - Update time entry
- `POST /entries/<id>/delete` - Delete time entry

**Sheet Routes (`sheets.py`):**

- `GET /` - Daily sheet view
- `GET /sheets/<date>` - Specific date sheet
- `POST /sheets/<date>/lock` - Lock/unlock sheet

**Schedule Routes (`schedule.py`):**

- `POST /schedule/<date>/import` - Import from Amion

**Resident Routes (`residents.py`):**

- `GET /residents` - Resident management page
- `POST /residents/add` - Add resident
- `POST /residents/<id>/toggle` - Toggle active status
- `POST /residents/import_staff` - Import from Amion

**Role Routes (`roles.py`):**

- `GET /roles` - Role configuration page
- `POST /roles/<id>/update` - Update role cutoff

**Report Routes (`reports.py`):**

- `GET /reports` - Report generation page
- `POST /generate_report` - Generate report
- `POST /export_report_csv` - CSV export
- `POST /email_report` - Send email report

**Holiday Routes (`holidays.py`):**

- `GET /holidays` - Holiday management page
- `POST /holidays/add` - Add custom holiday
- `POST /holidays/<id>/delete` - Delete holiday

**Audit Routes (`audit.py`):**

- `GET /audit` - Audit log viewer

### 3. Database Models (`backend/models.py`)

**Models:**

- `Resident` - Medical resident information
  - Methods: `get_active()`, `get_by_epic_id()`, `get_or_create()`, `to_dict()`
- `Role` - Shift roles (ECC 1-5, ECA, backup roles, etc.)
  - 18 default roles configured
- `TimeEntry` - Individual shift records
  - Property: `entry.overtime_hours`
- `DailySheet` - Sheet metadata (locked, submitted)
- `AuditLog` - Change tracking
- `Holiday` - Custom and federal holidays

**Business Logic:**

- `TimeEntry.overtime_hours` - Calculates overtime based on role cutoff and
  holiday awareness
- `Resident.get_or_create()` - Finds or creates resident by EPIC ID
- `Holiday` utilities for federal and custom holidays

### 4. Authentication & Authorization (`backend/auth.py`)

**No Login System:**

- Authentication handled externally (SSO, reverse proxy)
- User identity from `USER_NAME` environment variable

**Authorization:**

```python
def get_current_user() -> str:
    """Get current user from environment."""
    return os.getenv('USER_NAME', 'Unknown')

def is_admin() -> bool:
    """Check if current user is admin."""
    admin_users = os.getenv('ADMIN_USERS', '').split(',')
    return get_current_user() in admin_users

def admin_required(f):
    """Decorator to restrict route to admins."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
```

### 5. Audit Logging (`backend/audit.py`)

**Helper Functions:**

```python
def log_action(action, entity_type, entity_id, details, user=None):
    """Log an action to the audit trail."""
    # Captures user, IP, timestamp automatically

def log_create(entity_type, entity_id, details):
    """Log CREATE action."""

def log_update(entity_type, entity_id, changes):
    """Log UPDATE action with change details."""

def log_delete(entity_type, entity_id, details):
    """Log DELETE action."""

def log_lock(date, locked):
    """Log sheet LOCK/UNLOCK."""

def log_import(date, entries_count):
    """Log schedule IMPORT."""
```

**Automatic Data Capture:**

- User from `USER_NAME` environment variable
- IP address from request headers (X-Forwarded-For, X-Real-IP, or remote_addr)
- Timestamp in UTC
- Change details serialized to JSON

### 6. Email Service (`backend/email_service.py`)

**Functionality:**

- Send overtime reports via SMTP
- HTML email templates
- CSV attachment generation
- Configurable recipient list

**Process:**

1. Generate report data for date range
2. Build HTML email with summary statistics
3. Create CSV attachment with detailed data
4. Send via SMTP server

### 7. Holiday Management (`backend/holidays.py`)

**Features:**

- US federal holiday detection (using `holidays` library)
- Custom holiday CRUD operations
- Recurring holiday support
- Holiday-aware overtime calculations

**Federal Holidays:**

- New Year's Day, MLK Day, Presidents Day, Memorial Day
- Independence Day, Labor Day, Columbus Day
- Veterans Day, Thanksgiving, Christmas Day

### 8. Utilities (`backend/utils.py`)

**Functions:**

- `setup_logging()` - Configures application logging
- `get_client_ip()` - Extracts client IP from request
- Database backup utilities
- Error handling helpers

### 9. Forms (`backend/forms.py`)

**Form Classes:**

- `TimeEntryForm` - Validates time entries with CSRF
- `ResidentForm` - Validates resident names
- `RoleUpdateForm` - Validates role cutoff hours
- `ReportForm` - Validates date ranges
- `HolidayForm` - Validates holiday data

All forms include CSRF protection via Flask-WTF.

## Data Flow

### Adding a Time Entry

```
User submits form
    ↓
Flask route (POST /entries/add)
    ↓
CSRF token validation ✅
    ↓
Form validation (WTForms)
    ↓
Parse form data
    ↓
Check sheet lock status
    ↓
Create TimeEntry model
    ↓
SQLAlchemy saves to DB
    ↓
Log CREATE action to audit trail
    ↓
Redirect to sheet view
```

### Schedule Import Process

```
Admin clicks Import
    ↓
Flask route (POST /schedule/<date>/import)
    ↓
Fetch CSV from Amion API
    ↓
Parse CSV data
    ↓
For each resident assignment:
    ↓
    Extract EPIC ID
    ↓
    Find or create Resident by EPIC ID
    ↓
    Create TimeEntry for role
    ↓
Commit all changes
    ↓
Log IMPORT action with entry count
    ↓
Redirect with success message
```

### Staff Import Process

```
Admin clicks Import Staff
    ↓
Flask route (POST /residents/import_staff)
    ↓
Fetch staff list from Amion API (Report 706)
    ↓
Parse resident information
    ↓
For each resident:
    ↓
    Extract: name, EPIC ID, class year, email, phone
    ↓
    Find or create Resident
    ↓
    Update resident data
    ↓
Commit all changes
    ↓
Log IMPORT action
    ↓
Redirect with success message
```

### Email Report Process

```
Admin generates report
    ↓
Admin clicks "Email Report"
    ↓
Flask route (POST /email_report)
    ↓
Generate report data for date range
    ↓
Build HTML email template
    ↓
Create CSV attachment
    ↓
Send via SMTP
    ↓
Log action
    ↓
Show success/failure message
```

## Configuration

### Environment Variables

```env
# Required
SECRET_KEY                    # Flask secret (CSRF, sessions)
DATABASE_URL                  # SQLite database path
USER_NAME                     # Current user identity
ADMIN_USERS                   # Comma-separated admin list

# Email Configuration
EMAIL_HOST                    # SMTP server
EMAIL_PORT                    # SMTP port (587)
EMAIL_USERNAME                # SMTP username
EMAIL_PASSWORD                # SMTP password
EMAIL_RECIPIENT               # Report recipient

# Optional
TIMEZONE                      # Default: America/New_York
DEFAULT_CUTOFF_HOUR          # Default: 17 (5 PM)
DEFAULT_CUTOFF_MINUTE        # Default: 30
PORT                         # Default: 5000
```

### Role-Specific Cutoffs

Configured in database, editable via UI:

- ECA 1, ECA 2: 17:30
- ECC 1-5: 17:30
- PPMC: 17:30
- Late Late 1-2: 17:30
- Backup roles: Special handling

## Security Architecture

### Implemented ✅

1. **CSRF Protection**

   - Flask-WTF CSRFProtect enabled
   - All POST requests require token
   - Tokens in all templates

2. **Input Validation**

   - WTForms schema validation
   - Type coercion (strings → dates/times)
   - Length limits enforced

3. **SQL Injection Prevention**

   - SQLAlchemy ORM (parameterized queries)
   - No raw SQL execution
   - Use of `db.session.get()` for safe queries

4. **XSS Prevention**

   - Jinja2 auto-escaping enabled
   - All user input escaped

5. **Error Handling**

   - Custom exception classes
   - Try-catch blocks on all DB operations
   - Graceful degradation
   - Error logging

6. **Logging**

   - Application logging configured
   - All errors logged
   - Audit trail for all actions

7. **Authorization**
   - `@admin_required` decorator
   - Environment-based admin list
   - Protected routes for sensitive operations

### Not Implemented ❌

1. **Authentication**

   - No user login system
   - No password management
   - Must use external auth (SSO, reverse proxy)

2. **Rate Limiting**

   - No request throttling
   - Vulnerable to abuse without external protection

3. **HTTPS**

   - HTTP only (local dev)
   - Must configure SSL/TLS in production

4. **Session Management**
   - No session tracking
   - No user context persistence

## Deployment Architecture

### Internal (Current) ✅

```
┌──────────────────────────┐
│   Institutional Network  │
│      (Firewall)          │
│  ┌────────────────────┐  │
│  │  Flask Dev Server  │  │
│  │  localhost:5000    │  │
│  └────────────────────┘  │
│           │              │
│           ▼              │
│  ┌────────────────────┐  │
│  │  SQLite Database   │  │
│  └────────────────────┘  │
└──────────────────────────┘
```

## Testing Architecture

### Backend Testing (pytest)

**Coverage: 99%**

- 26 test modules
- ~7,500 lines of test code
- Fixtures in `conftest.py`
- Markers: unit, integration, slow, timezone, overtime

**Test Categories:**

- Model tests (database operations)
- Route tests (HTTP endpoints)
- Utility tests (helpers and functions)
- Integration tests (end-to-end flows)

### Frontend Testing (Jest)

**Coverage: 78%**

- 4 test suites
- ~1,564 lines of test code
- DOM mocking
- User interaction testing

**Test Categories:**

- Utility function tests
- UI interaction tests
- Date/time handling tests
- Report generation tests

### CI/CD Pipeline

GitHub Actions workflow:

1. **Backend Tests** - Python 3.13, pytest with coverage
2. **Frontend Tests** - Bun, Jest with coverage
3. **Build & Lint** - Prettier, Stylelint, Vite
4. **Security Scan** - Bandit
5. **Coverage Upload** - Codecov

## Monitoring & Operations

### Logs

- **Location:** Application logs in `logs/`
- **Contents:** Errors, imports, email sends, audit actions
- **Format:** Structured logging with timestamps

### Backups

- **Strategy:** File-based SQLite backups
- **Retention:** Manual or automated via scripts
- **RPO:** Depends on backup frequency

### Health Checks

```bash
# Check if app is running
curl http://localhost:5000/

# Check logs
tail -f logs/app.log

# Test database
uv run flask --app backend.app shell
>>> from backend.models import Resident
>>> Resident.query.count()

# Test email
# Configure SMTP and test via UI
```

## Technology Decisions

### Why SQLite?

- Single institution (no multi-tenancy)
- Sequential writes (no concurrency)
- Small dataset (< 10K entries/year)
- Zero maintenance
- File-based backups
- Perfect for this use case

### Why Flask?

- Simple CRUD application
- No complex routing needed
- Easy integration with SQLAlchemy
- Excellent Jinja2 templating
- Lightweight and fast

### Why Vanilla JS?

- Minimal interactivity needed
- No state management complexity
- Faster page loads
- Easier to maintain
- No build complexity (Vite bundles vendors only)

### Why Route Blueprints?

- Better code organization
- Easier to maintain and test
- Clear separation of concerns
- Modular architecture

### Why Jest for Frontend?

- Industry standard
- Good ES6 module support
- Built-in mocking
- Coverage reporting
