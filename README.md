# ECC Sheet — Medical Shift Tracking System

A comprehensive Flask-based web application for tracking medical resident shifts, calculating overtime, and generating reports with full audit logging.

**Status:** Production-ready | **Test Coverage:** 99% backend, 78% frontend

## Features

- **Daily Shift Management**
  - Inline time editing with 24-hour format
  - Automatic time rounding to 5-minute increments (always rounds up)
  - Automatic overtime calculation based on configurable cutoff times
  - Sheet locking with user tracking
  - Import schedules from Amion API
  - Backup role support with start/exit times
  - Copy to clipboard and print for signing

- **Staff Management**
  - Import staff from Amion (Report 706)
  - Track class year, email, phone, EPIC ID
  - Active/inactive status
  - Backup resident assignments

- **Holiday Management**
  - US federal holidays (automatic)
  - Custom holidays with recurring support
  - Holiday-aware overtime calculations

- **Comprehensive Reporting**
  - Quick reports (Last 7/30/90 days)
  - Custom date range reports
  - Resident-specific filtering
  - Detailed CSV export (date, role, times, overtime)
  - Billing CSV export (resident name, total overtime)
  - Email reports with payroll-style summaries

- **Audit Trail**
  - Complete change tracking for all operations
  - Enhanced logging with old/new value tracking
  - User and IP address logging
  - Filterable by action type and entity
  - Timestamps for all actions

- **Admin Features**
  - Resident management with EPIC ID support
  - Role configuration with customizable cutoff times (hour and minute)
  - Holiday management
  - Full audit log access
  - Email reporting

## Quick Start

### Prerequisites

- Python 3.13
- Bun (JavaScript runtime)
- Git

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd ecc-sheet

# Backend setup
uv venv
source .venv/bin/activate
uv sync

# Frontend setup
bun install
bun run build

# Apply database migrations
uv run flask --app backend.app db upgrade

# Run application
uv run python -m backend.app
```

Visit: `http://localhost:5000`

## Configuration

Create a `.env` file in the project root:

```env
# Required
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///ecc_sheet.db
USER_NAME=Admin

# Admin access (comma-separated list)
ADMIN_USERS=Admin,John Doe,Jane Smith

# Email Configuration (for reports)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USERNAME=user@example.com
EMAIL_PASSWORD=password
EMAIL_RECIPIENT=recipient@example.com

# Amion Integration (for schedule/staff imports)
AMION_SCHEDULE_CODE=your-schedule-code-here

# Optional
TIMEZONE=America/New_York
PORT=5000
```

See `.env.example` for a complete template.

## Tech Stack

### Backend

- **Python 3.13** with Flask 3.1.2
- **SQLite** - File-based database with migration support
- **SQLAlchemy** - ORM with relationship management
- **Flask-Migrate 4.1.0 (Alembic)** - Database version control
- **Flask-WTF 1.2.2** - Form validation with CSRF protection
- **pytz 2025.2** - Timezone handling
- **holidays 0.89** - US federal holiday tracking

### Frontend

- **Jinja2** - Server-side templates with 24-hour time format
- **Vanilla JavaScript** - ES6+ with Luxon for timezone handling
- **Bootstrap 5.3.8** - UI framework (bundled locally)
- **Bootstrap Icons 1.13.1** - Icon library
- **Luxon 3.7.2** - DateTime library with timezone support
- **Vite 7.3.1** - Build tool for asset bundling
- **Prettier 3.8.1** - Code formatter

### Testing

- **pytest 9.0.2** - Python testing framework (99% coverage)
- **Jest 30.2.0** - JavaScript testing framework (78% coverage)
- **GitHub Actions** - Automated CI/CD pipeline
- **Codecov** - Coverage tracking and reporting

### Build Tools

- **UV** - Python package manager
- **Bun** - JavaScript runtime and package manager
- **Vite** - Frontend build tool
- **Ruff** - Python linting
- **Stylelint** - CSS linting

## Development

### Backend Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=backend --cov-report=html

# Run application with auto-reload
uv run python -m backend.app
```

### Frontend Development

```bash
# Install dependencies
bun install

# Build for production
bun run build

# Watch mode for development
bun run dev

# Run tests
bun run test

# Run with coverage
bun run test:coverage

# Format code
bun run format

# Check formatting
bun run format:check

# Lint CSS
bun run lint:css
```

### Database Migrations

```bash
# Create migration after model changes
uv run flask --app backend.app db migrate -m "description"

# Apply migrations
uv run flask --app backend.app db upgrade

# Check current revision
uv run flask --app backend.app db current

# View migration history
uv run flask --app backend.app db history
```

## Project Structure

```
ecc-sheet/
├── backend/                 # Python backend
│   ├── app.py              # Main Flask application
│   ├── models.py           # Database models
│   ├── routes/             # Route blueprints (9 modules)
│   ├── audit.py            # Audit logging
│   ├── auth.py             # Authorization utilities
│   ├── config.py           # Configuration
│   ├── email_service.py    # Email reporting
│   ├── holidays.py         # Holiday utilities
│   ├── report_utils.py     # Report generation utilities
│   └── staff_import.py     # Amion staff parsing
├── frontend/                # Frontend templates and assets
│   ├── templates/          # Jinja2 templates
│   └── static/
│       ├── dist/           # Vite build output
│       ├── js/             # JavaScript source
│       │   └── __tests__/  # Jest test suites
│       └── css/            # Stylesheets
├── migrations/              # Database migrations
├── tests/                   # Python test suite (26 modules)
├── docs/                    # Documentation
├── scripts/                 # Utility scripts
└── instance/                # Instance files (database)
```

## Authentication & Authorization

The application uses environment-based authentication:

- **User Identity**: Set via `USER_NAME` environment variable
- **Admin Access**: Controlled by `ADMIN_USERS` (comma-separated list)
- **External Auth**: Designed to work with SSO or reverse proxy

Authentication must be handled externally (e.g., institutional SSO, reverse proxy).

## Security

### Current Protections

- CSRF protection for all forms
- SQL injection prevention via SQLAlchemy ORM
- XSS protection via Jinja2 auto-escaping
- Input validation with WTForms
- Complete audit trail with IP tracking
- Confirmation dialogs for destructive actions
- Email validation for reports

### Production Requirements

- External authentication system (SSO recommended)
- HTTPS/SSL encryption
- Rate limiting (Flask-Limiter)
- Production WSGI server (gunicorn, uwsgi)
- Regular database backups
- Security audit before internet deployment

## API Endpoints

### Data Endpoints (GET)

- `/api/residents/active` - List active residents
- `/api/roles` - List all roles

### Form Endpoints (POST)

- `/entries/add` - Add time entry
- `/entries/<id>/update` - Update time entry (with audit logging)
- `/entries/<id>/delete` - Delete time entry (with audit logging)
- `/sheets/<date>/lock` - Toggle sheet lock
- `/schedule/<date>/import` - Import from Amion
- `/residents/add` - Add resident
- `/residents/<id>/toggle` - Toggle resident status
- `/residents/import_staff` - Import staff from Amion
- `/roles/<id>/update` - Update role cutoff
- `/holidays/add` - Add custom holiday
- `/holidays/<id>/delete` - Delete holiday
- `/api/report` - Generate overtime reports
- `/api/report/export_csv` - Export detailed report as CSV
- `/api/report/export_billing_csv` - Export billing/payroll summary as CSV
- `/api/report/send_email` - Send reports via email

All POST endpoints require CSRF token.

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive project documentation
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture reference
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
- **[docs/README.md](docs/README.md)** - Documentation overview

## Testing

```bash
# Run all backend tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=backend --cov-report=html

# Run specific test file
uv run pytest tests/test_models.py -v

# Run frontend tests
bun run test

# Run with coverage
bun run test:coverage
```

### Test Coverage

- **Backend:** 99% coverage (26 test modules, ~7,500 lines)
- **Frontend:** 78% coverage (4 test suites)
- **CI/CD:** GitHub Actions with automated testing
- **Coverage Reporting:** Codecov integration

## CI/CD Pipeline

GitHub Actions workflow includes:

1. **Backend Tests** - Python 3.13, pytest with coverage
2. **Frontend Tests** - Bun, Jest with coverage
3. **Frontend Build & Lint** - Prettier, Stylelint, Vite build
4. **Security Scan** - Bandit security analysis
5. **Coverage Upload** - Codecov reporting

## Troubleshooting

### Database Issues

- **Database locked**: SQLite write locks - usually resolves on retry
- **Migration conflicts**: Run `uv run flask --app backend.app db history` to view

### Frontend Issues

- **Vite build fails**: Clear `node_modules` and reinstall with `bun install`
- **Icons not displaying**: Rebuild assets with `bun run build`

### Import Issues

- **Schedule import fails**: Verify Amion URL accessibility
- **Staff import fails**: Check Amion API access and Report 706 format
- **Missing residents**: Ensure EPIC IDs are populated

### Email Issues

- **Email reports not sending**: Verify SMTP configuration in `.env`
- **Check credentials**: EMAIL_HOST, EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD

See `CLAUDE.md` for detailed troubleshooting.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Code style and formatting
- Testing requirements (99% backend, 78% frontend)
- Pull request process
- Database migration workflow
- Route blueprint organization

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Changelog

### Version 3.1 (2026-02-11)

- Changed time rounding from 15-minute to 5-minute increments
- Added billing/payroll CSV export (resident name + total overtime)
- Enhanced audit logging with old/new value tracking
- Simplified email reports to payroll format (name + total only)
- Moved Amion schedule code to environment variable (AMION_SCHEDULE_CODE)
- Updated all documentation and setup scripts

**Migration Note:** Add `AMION_SCHEDULE_CODE=your-schedule-code-here` to your `.env` file

### Version 3.0 (2026-01-31)

- Added holiday management system
- Added staff import from Amion (Report 706)
- Added email reporting with CSV attachments
- Added backup role support
- Implemented route blueprint architecture
- Increased test coverage to 99% backend, 78% frontend
- Added Jest frontend testing
- Added GitHub Actions CI/CD
- Code quality improvements and refactoring

### Version 2.0 (2025-11-25)

- Simplified authentication to environment-based
- Added comprehensive audit logging
- Migrated to Vite for frontend bundling
- Implemented 24-hour time format
- Added Prettier code formatting
- Enhanced UX with loading states and confirmations
- Full hour/minute editing for role cutoffs

### Version 1.0

- Initial release
- Daily shift tracking
- Overtime calculations
- Report generation

## Support

For issues, questions, or contributions, please open an issue on GitHub.
