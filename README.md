# ECC Sheet - Medical Shift Tracking System

A comprehensive Flask-based web application for tracking medical resident
shifts, calculating overtime, and generating reports with full audit logging.

**Status:** Production-ready with enhanced UX | Requires external authentication
for deployment

## Features

- **Daily Shift Management**

  - Inline time editing with 24-hour format
  - Automatic overtime calculation based on configurable cutoff times
  - Sheet locking with user tracking
  - Import schedules from Amion API

- **Comprehensive Reporting**

  - Quick reports (Last 7/30/90 days)
  - Custom date range reports
  - Resident-specific filtering
  - CSV export functionality

- **Audit Trail**

  - Complete change tracking for all operations
  - User and IP address logging
  - Filterable by action type and entity
  - Timestamps for all actions

- **Admin Features**
  - Resident management with EPIC ID support
  - Role configuration with customizable cutoff times
  - Full audit log access

## Quick Start

### Prerequisites

- Python 3.11+
- Bun (JavaScript runtime)
- Git

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd ecc-sheet

# Backend setup
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

# Optional
TIMEZONE=America/New_York
PORT=5000
```

See `.env.example` for a complete template.

## Tech Stack

### Backend

- **Python 3.11+** with Flask 3.0
- **SQLite** - File-based database with migration support
- **SQLAlchemy** - ORM with relationship management
- **Flask-Migrate (Alembic)** - Database version control
- **Flask-WTF** - Form validation with CSRF protection

### Frontend

- **Jinja2** - Server-side templates with 24-hour time format
- **Vanilla JavaScript** - ES6+ with Luxon for timezone handling
- **Bootstrap 5.3.8** - UI framework (bundled locally)
- **Bootstrap Icons 1.13.1** - Icon library
- **Luxon 3.7.2** - DateTime library with timezone support
- **Vite 7.2.4** - Build tool for asset bundling
- **Prettier 3.6.2** - Code formatter

### Build Tools

- **Bun** - JavaScript runtime and package manager
- **Vite** - Frontend build tool
- **UV** - Python package manager

## Development

### Backend Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

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

See `docs/DATABASE_MIGRATIONS.md` for detailed migration workflow.

## Project Structure

```
ecc-sheet/
├── backend/                 # Python backend
│   ├── app.py              # Main Flask application
│   ├── models.py           # Database models
│   ├── audit.py            # Audit logging
│   ├── auth.py             # Authorization utilities
│   └── config.py           # Configuration
├── frontend/                # Frontend templates and assets
│   ├── templates/          # Jinja2 templates
│   └── static/
│       ├── dist/           # Vite build output
│       ├── js/             # JavaScript source
│       └── css/            # Stylesheets
├── migrations/              # Database migrations
├── docs/                    # Documentation
├── tests/                   # Test files
└── instance/                # Instance files (database)
```

## Authentication & Authorization

The application uses environment-based authentication:

- **User Identity**: Set via `USER_NAME` environment variable
- **Admin Access**: Controlled by `ADMIN_USERS` (comma-separated list)
- **External Auth**: Designed to work with SSO or reverse proxy

Authentication must be handled externally (e.g., institutional SSO, reverse
proxy).

## Security

### Current Protections

- CSRF protection on all forms
- SQL injection prevention via SQLAlchemy ORM
- XSS protection via Jinja2 auto-escaping
- Input validation with WTForms
- Complete audit trail with IP tracking
- Confirmation dialogs for destructive actions

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
- `/entries/<id>/update` - Update time entry
- `/entries/<id>/delete` - Delete time entry
- `/sheets/<date>/lock` - Toggle sheet lock
- `/schedule/<date>/import` - Import from Amion
- `/residents/add` - Add resident
- `/residents/<id>/toggle` - Toggle resident status
- `/roles/<id>/update` - Update role cutoff
- `/generate_report` - Generate overtime report
- `/export_report_csv` - Export report as CSV

All POST endpoints require CSRF token.

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive project documentation
- **[DATABASE_MIGRATIONS.md](docs/DATABASE_MIGRATIONS.md)** - Migration workflow
  guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=backend --cov-report=html

# Run specific test file
uv run pytest tests/test_models.py -v
```

## Troubleshooting

### Database Issues

- **Database locked**: SQLite write locks - usually resolves on retry
- **Migration conflicts**: Run `uv run flask --app backend.app db history` to
  view

### Frontend Issues

- **Vite build fails**: Clear `node_modules` and reinstall with `bun install`
- **Icons not displaying**: Rebuild assets with `bun run build`

### Import Issues

- **Schedule import fails**: Verify Amion URL accessibility
- **Missing residents**: Ensure EPIC IDs are populated

See `CLAUDE.md` for detailed troubleshooting.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Code style and formatting
- Testing requirements
- Pull request process
- Database migration workflow

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Changelog

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
