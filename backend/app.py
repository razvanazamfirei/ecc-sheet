from logging import Logger
from pathlib import Path

from flask import Flask, request
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from backend.background_services import (
    should_start_background_services_during_import,
)
from backend.background_services import (
    start_background_services as _start_background_services,
)
from backend.cli import register_cli_commands
from backend.config import env_str, get_flask_config, get_settings
from backend.database.bootstrap import init_db as _init_db
from backend.database.runtime_schema import (
    ensure_runtime_schema as _ensure_runtime_schema_for_app,
)
from backend.email_service import init_email_service
from backend.models import db
from backend.routes import register_blueprints
from backend.security.flask import configure_security
from backend.utils import setup_logging

# Get the project root directory (parent of backend/)
project_root: Path = Path(__file__).parent.parent

app: Flask = Flask(
    __name__,
    template_folder=str(project_root / "frontend" / "templates"),
    static_folder=str(project_root / "frontend" / "static"),
)
settings = get_settings()
app.config.from_mapping(get_flask_config())

if settings.FLASK_ENV == "production" and not env_str("SECRET_KEY"):
    raise RuntimeError(
        "A strong SECRET_KEY must be set in production. "
        "Refusing to start without an explicit SECRET_KEY."
    )

db.init_app(app)
init_email_service(app)

# Initialize Flask-Migrate for database migrations
migrate: Migrate = Migrate(app, db, render_as_batch=True)

csrf: CSRFProtect = CSRFProtect(app)


logger: Logger = setup_logging()

register_blueprints(app)
configure_security(app, csrf)


@app.after_request
def apply_security_headers(response):
    """Apply optional response headers from configuration."""
    csp_policy = app.config.get("CSP_POLICY")
    if csp_policy:
        response.headers.setdefault("Content-Security-Policy", str(csp_policy))
    return response


def _ensure_runtime_schema() -> None:
    """Ensure required tables and additive columns exist for this process."""
    _ensure_runtime_schema_for_app(app, logger=logger)


def _bootstrap_database() -> None:
    """Bootstrap schema and default data for the current app."""
    _init_db(app, ensure_runtime_schema=_ensure_runtime_schema)


def _ensure_runtime_schema_callback() -> None:
    """CLI callback that resolves the current runtime-schema function."""
    _ensure_runtime_schema()


def _bootstrap_database_callback() -> None:
    """CLI callback that resolves the current database-bootstrap function."""
    _bootstrap_database()


@app.before_request
def ensure_runtime_schema() -> None:
    """Ensure runtime schema before handling non-static requests."""
    if request.endpoint == "static" or app.extensions.get("runtime_schema_checked"):
        return

    _ensure_runtime_schema()


register_cli_commands(
    app,
    ensure_runtime_schema=_ensure_runtime_schema_callback,
    init_db=_bootstrap_database_callback,
)


if should_start_background_services_during_import(module_name=__name__):
    _start_background_services(app, _ensure_runtime_schema)


if __name__ == "__main__":
    _bootstrap_database()
    _start_background_services(app, _ensure_runtime_schema)
    # Always use debug=False for security
    port = int(env_str("PORT", "5000"))
    app.run(debug=False, host="0.0.0.0", port=port)
