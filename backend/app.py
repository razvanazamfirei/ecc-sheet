from logging import Logger
from pathlib import Path

from flask import Flask, session
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from .auth import get_current_user, is_admin
from .config import Config
from .holidays import get_federal_holidays
from .models import Holiday, Resident, Role, db
from .routes import register_blueprints
from .utils import get_effective_date, setup_logging

# Get the project root directory (parent of backend/)
project_root: Path = Path(__file__).parent.parent

app: Flask = Flask(
    __name__,
    template_folder=str(project_root / "frontend" / "templates"),
    static_folder=str(project_root / "frontend" / "static"),
)
app.config.from_object(Config)
db.init_app(app)

# Initialize Flask-Migrate for database migrations
migrate: Migrate = Migrate(app, db, render_as_batch=True)

# Enable CSRF protection
csrf: CSRFProtect = CSRFProtect(app)

# Setup logging
logger: Logger = setup_logging()

# Register all route blueprints
register_blueprints(app)

# Exempt the dev blueprint from CSRF only when mock users are enabled
import os as _os  # noqa: E402
import warnings as _warnings  # noqa: E402

from .routes import dev as _dev_module  # noqa: E402

_mock_enabled = _os.getenv("MOCK_USERS_ENABLED", "").lower() in {"1", "true", "yes"}
if _mock_enabled:
    if _os.getenv("FLASK_ENV", "").lower() == "production":
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


# Make auth functions available in templates
@app.context_processor
def inject_auth():
    """Inject authentication functions into template context."""
    return {"current_user": get_current_user(), "is_admin": is_admin()}


@app.context_processor
def inject_dev():
    """Inject dev mock-user context (only when MOCK_USERS_ENABLED is set)."""
    import os  # noqa: PLC0415

    if os.getenv("MOCK_USERS_ENABLED", "").lower() not in {"1", "true", "yes"}:
        return {"mock_users_enabled": False}

    admin_users = [
        u.strip() for u in os.getenv("ADMIN_USERS", "Admin").split(",") if u.strip()
    ]
    payroll_users = [
        u.strip() for u in os.getenv("PAYROLL_ADMIN_USERS", "").split(",") if u.strip()
    ]

    personas = [{"name": admin_users[0] if admin_users else "Admin", "label": "Admin"}]
    if payroll_users:
        personas.append({"name": payroll_users[0], "label": "Payroll Admin"})
    personas.append({"name": "Regular Viewer", "label": "Regular Viewer"})

    try:
        residents = Resident.query.filter_by(active=True).order_by(Resident.name).all()
        resident_names = [r.name for r in residents]
    except Exception:
        app.logger.exception("Failed to query residents for dev mock context")
        resident_names = []

    return {
        "mock_users_enabled": True,
        "mock_personas": personas,
        "mock_residents": resident_names,
        "dev_user_override": session.get("dev_user"),
    }


def init_db():
    """Initialize database with default roles"""
    with app.app_context():
        db.create_all()

        # Backup role names
        backup_roles = {"Backup", "Cardiac Backup", "Moonlighting"}

        # Call team roles: displayed on sheet but never generate overtime
        call_team_roles = {
            "First Call",
            "Second Call",
            "Third Call",
            "OB Flex",
            "Cardiac Call",
        }

        # Create default roles if they don't exist
        default_roles = [
            ("ECA 1", 1),
            ("ECA 2", 2),
            ("ECC 1", 3),
            ("ECC 2", 4),
            ("ECC 3", 5),
            ("ECC 4", 6),
            ("ECC 5", 7),
            ("PPMC", 8),
            ("Late Late 1", 9),
            ("Late Late 2", 10),
            ("Held", 11),
            ("EP/HUP 13", 12),
            ("H12", 13),
            ("H13", 14),
            ("H14", 15),
            ("HUP EP 12", 16),
            ("Backup", 17),
            ("Cardiac Backup", 18),
            ("Moonlighting", 19),
            ("First Call", 20),
            ("Second Call", 21),
            ("Third Call", 22),
            ("Cardiac Call", 23),
            ("OB Flex", 24),
        ]

        for role_name, order in default_roles:
            existing_role = Role.query.filter_by(name=role_name).first()
            if not existing_role:
                cutoff_hour = app.config["ROLE_CUTOFF_HOURS"].get(
                    role_name, app.config["DEFAULT_CUTOFF_HOUR"]
                )
                cutoff_minute = app.config["ROLE_CUTOFF_MINUTES"].get(
                    role_name, app.config["DEFAULT_CUTOFF_MINUTE"]
                )
                role = Role(
                    name=role_name,
                    cutoff_hour=cutoff_hour,
                    cutoff_minute=cutoff_minute,
                    display_order=order,
                    is_backup=(role_name in backup_roles),
                    is_call_team=(role_name in call_team_roles),
                )
                db.session.add(role)
            else:
                # Always correct categorical flags; only backfill display_order
                # if unset so admin-customized ordering is preserved.
                existing_role.is_backup = role_name in backup_roles
                existing_role.is_call_team = role_name in call_team_roles
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
