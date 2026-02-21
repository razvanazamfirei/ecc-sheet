from pathlib import Path

from flask import Flask
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from .auth import get_current_user, is_admin
from .config import Config
from .holidays import get_federal_holidays
from .models import Holiday, Role, db
from .routes import register_blueprints
from .utils import get_effective_date, setup_logging

# Get the project root directory (parent of backend/)
project_root = Path(__file__).parent.parent

app = Flask(
    __name__,
    template_folder=str(project_root / "frontend" / "templates"),
    static_folder=str(project_root / "frontend" / "static"),
)
app.config.from_object(Config)
db.init_app(app)

# Initialize Flask-Migrate for database migrations
migrate = Migrate(app, db)

# Enable CSRF protection
csrf = CSRFProtect(app)

# Setup logging
logger = setup_logging()

# Register all route blueprints
register_blueprints(app)


# Make auth functions available in templates
@app.context_processor
def inject_auth():
    """Inject authentication functions into template context."""
    return {"current_user": get_current_user(), "is_admin": is_admin()}


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
