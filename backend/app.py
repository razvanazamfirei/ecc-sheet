import os
import warnings as _warnings
from logging import Logger
from pathlib import Path

from flask import Flask, jsonify, request, session
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import SQLAlchemyError

from .auth import (
    get_admin_users,
    get_current_user,
    get_payroll_admin_users,
    is_admin,
    mock_users_enabled,
)
from .config import Config
from .holidays import get_federal_holidays
from .instance_config import (
    BACKUP_ROLE_NAMES,
    CALL_TEAM_ROLE_NAMES,
    DEFAULT_CUTOFF_HOUR,
    DEFAULT_CUTOFF_MINUTE,
    DEFAULT_ROLES,
    ROLE_CUTOFF_HOURS,
    ROLE_CUTOFF_MINUTES,
)
from .models import Holiday, Resident, Role, db
from .routes import dev as _dev_module
from .routes import register_blueprints
from .utils import _wants_json_response, get_effective_date, setup_logging
from .utils.email_service import init_email_service

# Get the project root directory (parent of backend/)
project_root: Path = Path(__file__).parent.parent

app: Flask = Flask(
    __name__,
    template_folder=str(project_root / "frontend" / "templates"),
    static_folder=str(project_root / "frontend" / "static"),
)
app.config.from_object(Config)

if app.config.get("FLASK_ENV") == "production":
    configured_secret_key = (os.getenv("SECRET_KEY") or "").strip()
    if not configured_secret_key:
        raise RuntimeError(
            "A strong SECRET_KEY must be set in production. "
            "Refusing to start without an explicit SECRET_KEY."
        )

db.init_app(app)
init_email_service(app)

# Initialize Flask-Migrate for database migrations
migrate: Migrate = Migrate(app, db, render_as_batch=True)

# Enable CSRF protection
csrf: CSRFProtect = CSRFProtect(app)


def _authentication_required_response():
    """Return a 401 response when proxy-auth identity is missing."""
    message = "Authentication required."
    if _wants_json_response():
        return jsonify({"success": False, "message": message}), 401
    return message, 401


# Setup logging
logger: Logger = setup_logging()

# Register all route blueprints
register_blueprints(app)


def _build_mock_personas() -> list[dict[str, str]]:
    """Return the available dev personas for the mock-user dropdown."""
    admin_users = get_admin_users()
    payroll_users = get_payroll_admin_users()

    personas = [{"name": admin_users[0] if admin_users else "Admin", "label": "Admin"}]
    if payroll_users:
        personas.append({"name": payroll_users[0], "label": "Payroll Admin"})
    personas.append({"name": "Regular Viewer", "label": "Regular Viewer"})
    return personas


def _active_resident_names() -> list[str]:
    """Return active resident names for the dev mock-user dropdown."""
    try:
        residents = Resident.query.filter_by(active=True).order_by(Resident.name).all()
    except SQLAlchemyError:
        app.logger.exception("Failed to query residents for dev mock context")
        return []

    return [resident.name for resident in residents]


if mock_users_enabled():
    if os.getenv("FLASK_ENV", "").lower() == "production":
        raise RuntimeError(
            "MOCK_USERS_ENABLED is set in a production environment. "
            "This enables unauthenticated user impersonation. Refusing to start."
        )
    _warnings.warn(
        "MOCK_USERS_ENABLED is active: dev user impersonation is enabled. "
        "Do not use in production.",
        stacklevel=1,
    )
    csrf.exempt(_dev_module.bp)


@app.before_request
def require_authenticated_request():
    """Fail closed when proxy-auth is enabled and the identity header is absent."""
    proxy_header = str(app.config.get("AUTH_PROXY_USERNAME_HEADER") or "").strip()
    if not proxy_header or mock_users_enabled() or request.endpoint == "static":
        return None

    if get_current_user():
        return None

    return _authentication_required_response()


# Make auth functions available in templates
@app.context_processor
def inject_auth():
    """Inject authentication functions into template context."""
    return {"current_user": get_current_user(), "is_admin": is_admin()}


@app.context_processor
def inject_dev():
    """Inject dev mock-user context (only when MOCK_USERS_ENABLED is set)."""
    if not mock_users_enabled():
        return {"mock_users_enabled": False}

    return {
        "mock_users_enabled": True,
        "mock_personas": _build_mock_personas(),
        "mock_residents": _active_resident_names(),
        "dev_user_override": session.get("dev_user"),
    }


@app.after_request
def apply_security_headers(response):
    """Apply optional response headers from configuration."""
    csp_policy = app.config.get("CSP_POLICY")
    if csp_policy:
        response.headers.setdefault("Content-Security-Policy", str(csp_policy))
    return response


def init_db():
    """Initialize database with default roles"""
    with app.app_context():
        db.create_all()

        for role_name, order in DEFAULT_ROLES:
            existing_role = Role.query.filter_by(name=role_name).first()
            if not existing_role:
                cutoff_hour = ROLE_CUTOFF_HOURS.get(role_name, DEFAULT_CUTOFF_HOUR)
                cutoff_minute = ROLE_CUTOFF_MINUTES.get(
                    role_name, DEFAULT_CUTOFF_MINUTE
                )
                role = Role(
                    name=role_name,
                    cutoff_hour=cutoff_hour,
                    cutoff_minute=cutoff_minute,
                    display_order=order,
                    is_backup=(role_name in BACKUP_ROLE_NAMES),
                    is_call_team=(role_name in CALL_TEAM_ROLE_NAMES),
                )
                db.session.add(role)
            else:
                # Always correct categorical flags; only backfill display_order
                # if unset so admin-customized ordering is preserved.
                existing_role.is_backup = role_name in BACKUP_ROLE_NAMES
                existing_role.is_call_team = role_name in CALL_TEAM_ROLE_NAMES
                if existing_role.display_order is None:
                    existing_role.display_order = order

        # Initialize federal holidays for current and next year
        current_year = get_effective_date().year
        for year in [current_year, current_year + 1]:
            for holiday_date, holiday_name in get_federal_holidays(year):
                if not Holiday.query.filter_by(date=holiday_date).first():
                    holiday = Holiday(
                        date=holiday_date,
                        name=holiday_name,
                        is_federal=True,
                    )
                    db.session.add(holiday)

        db.session.commit()


if __name__ == "__main__":
    import os

    init_db()
    # Always use debug=False for security
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=False, host="0.0.0.0", port=port)
