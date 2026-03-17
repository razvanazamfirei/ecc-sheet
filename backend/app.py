import os
import sys
import threading
import warnings as _warnings
from datetime import date, timedelta
from logging import Logger
from pathlib import Path
from typing import TextIO

import click
from flask import Flask, jsonify, redirect, request, session, url_for
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .anesthesia_sync import AnesthesiaSyncError, sync_anesthesia_stop_times
from .auth import (
    get_admin_users,
    get_current_user,
    get_payroll_admin_users,
    is_admin,
    mock_users_enabled,
)
from .config import Config
from .db_session import commit_or_rollback
from .email_service import init_email_service
from .errors import APIError
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
from .resident_csv_import import import_residents_csv_file
from .routes import dev as _dev_module
from .routes import register_blueprints
from .saml import (
    get_session_authenticated_user,
    saml_enabled,
    saml_public_endpoint,
)
from .utils import _wants_json_response, get_effective_date, setup_logging

try:
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - exercised in import-safe tests
    fcntl = None

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
_background_sync_lock = threading.Lock()
_runtime_schema_lock = threading.Lock()


def _authentication_required_response(*, redirect_to_login: bool = False):
    """Return an auth challenge for missing identity."""
    message = "Authentication required."
    if redirect_to_login and not _wants_json_response() and request.method == "GET":
        next_url = request.full_path.rstrip("?") or request.path
        return redirect(url_for("auth.login", next=next_url))
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
    """Fail closed when external auth is enabled and identity is absent."""
    if request.endpoint == "static" or mock_users_enabled():
        return None

    if saml_enabled(app.config):
        if not saml_public_endpoint(request.endpoint) and not get_current_user():
            return _authentication_required_response(redirect_to_login=True)
        return None

    proxy_header = str(app.config.get("AUTH_PROXY_USERNAME_HEADER") or "").strip()
    if proxy_header and not get_current_user():
        return _authentication_required_response()
    return None


# Make auth functions available in templates
@app.context_processor
def inject_auth():
    """Inject authentication functions into template context."""
    session_user = get_session_authenticated_user()
    return {
        "current_user": get_current_user(),
        "is_admin": is_admin(),
        "can_logout": bool(session_user and saml_enabled(app.config)),
    }


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


def _is_duplicate_column_error(exc: SQLAlchemyError, column_name: str) -> bool:
    """Return True when a schema ALTER failed because the column already exists."""
    messages = [str(exc)]
    original_error = getattr(exc, "orig", None)
    if original_error is not None and original_error is not exc:
        messages.append(str(original_error))

    normalized_message = " ".join(messages).casefold()
    normalized_column = column_name.casefold()
    duplicate_markers = ("duplicate column", "already exists")
    return normalized_column in normalized_message and any(
        marker in normalized_message for marker in duplicate_markers
    )


def _ensure_time_entry_columns() -> None:
    """Backfill nullable TimeEntry columns for existing databases."""
    inspector = sqlalchemy_inspect(db.engine)
    time_entry_columns = {
        column["name"] for column in inspector.get_columns("time_entries")
    }
    if "anesthesia_stop_time" not in time_entry_columns:
        try:
            commit_or_rollback(
                lambda: db.session.execute(
                    text(
                        "ALTER TABLE time_entries "
                        "ADD COLUMN anesthesia_stop_time TIME"
                    )
                )
            )
        except SQLAlchemyError as exc:
            if _is_duplicate_column_error(exc, "anesthesia_stop_time"):
                logger.info(
                    "Column anesthesia_stop_time already exists; "
                    "skipping runtime schema backfill.",
                )
                return
            raise


def _ensure_runtime_schema() -> None:
    """Ensure required tables and additive columns exist for this process."""
    with _runtime_schema_lock:
        if app.extensions.get("runtime_schema_checked"):
            return

        db.create_all()
        _ensure_time_entry_columns()
        app.extensions["runtime_schema_checked"] = True


def _auto_sync_window() -> tuple[date, date]:
    """Return the rolling date window for automatic anesthesia stop syncing."""
    effective_date = get_effective_date()
    lookback_days = max(
        0,
        int(app.config.get("ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS", 1)),
    )
    return effective_date - timedelta(days=lookback_days), effective_date


def _run_auto_anesthesia_sync_once() -> None:
    """Run one automatic anesthesia stop-time sync cycle."""
    with app.app_context():
        _ensure_runtime_schema()
        start_date, end_date = _auto_sync_window()
        result = sync_anesthesia_stop_times(
            start_date=start_date,
            end_date=end_date,
            overwrite_existing=False,
            dry_run=False,
            user="anesthesia-auto-sync",
        )
        logger.info("Automatic anesthesia stop-time sync: %s", result.summary())


def _auto_anesthesia_sync_loop(stop_event: threading.Event) -> None:
    """Run automatic anesthesia stop-time sync on a fixed interval."""
    interval_seconds = max(
        30,
        int(app.config.get("ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS", 120)),
    )
    logger.info(
        "Automatic anesthesia stop-time sync started (interval=%ss, lookback_days=%s).",
        interval_seconds,
        app.config.get("ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS", 1),
    )
    while not stop_event.is_set():
        try:
            _run_auto_anesthesia_sync_once()
        except Exception:
            logger.exception("Automatic anesthesia stop-time sync failed")

        if stop_event.wait(interval_seconds):
            break


def _background_service_lock_path() -> Path:
    """Return the process-lock path for the anesthesia auto-sync worker."""
    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)
    return instance_dir / "anesthesia-auto-sync.lock"


def _acquire_background_service_process_lock() -> TextIO | None:
    """Acquire a cross-process lock so only one worker runs auto-sync."""
    lock_handle = _background_service_lock_path().open("a+", encoding="utf-8")
    if fcntl is None:
        logger.warning(
            "fcntl is unavailable on this platform; continuing without a "
            "cross-process background-service lock.",
        )
        return lock_handle

    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_handle.close()
        return None

    lock_handle.seek(0)
    lock_handle.truncate()
    lock_handle.write(f"{os.getpid()}\n")
    lock_handle.flush()
    return lock_handle


def _release_background_service_process_lock(lock_handle: TextIO | None) -> None:
    """Release the cross-process lock for the anesthesia auto-sync worker."""
    if lock_handle is None:
        return

    if fcntl is None:
        lock_handle.close()
        return

    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        logger.debug("Background service lock was already released", exc_info=True)
    finally:
        lock_handle.close()


def start_background_services() -> bool:
    """Start background services once for the deployment."""
    if app.config.get("TESTING"):
        return False
    if not app.config.get("ANESTHESIA_FETCHER_ENABLED"):
        return False
    if app.debug and os.getenv("WERKZEUG_RUN_MAIN") != "true":
        return False

    started = False
    with _background_sync_lock:
        existing_service = app.extensions.get("anesthesia_auto_sync_service")
        if existing_service is None:
            try:
                lock_handle = _acquire_background_service_process_lock()
            except OSError:
                logger.exception(
                    "Failed to initialize the anesthesia auto-sync process lock"
                )
            else:
                if lock_handle is None:
                    logger.info(
                        "Skipping anesthesia auto-sync worker in pid=%s; "
                        "another process already owns the service lock.",
                        os.getpid(),
                    )
                else:
                    stop_event = threading.Event()
                    worker = threading.Thread(
                        target=_auto_anesthesia_sync_loop,
                        args=(stop_event,),
                        name="anesthesia-auto-sync",
                        daemon=True,
                    )
                    try:
                        worker.start()
                    except Exception:
                        _release_background_service_process_lock(lock_handle)
                        raise

                    app.extensions["anesthesia_auto_sync_service"] = {
                        "thread": worker,
                        "stop_event": stop_event,
                        "lock_handle": lock_handle,
                    }
                    started = True
    return started


def stop_background_services() -> bool:
    """Stop background services for the current process when running."""
    with _background_sync_lock:
        existing_service = app.extensions.pop("anesthesia_auto_sync_service", None)
        if existing_service is None:
            return False

        stop_event = existing_service["stop_event"]
        worker = existing_service["thread"]
        lock_handle = existing_service.get("lock_handle")
        stop_event.set()
        if worker.is_alive():
            worker.join(timeout=1)
        _release_background_service_process_lock(lock_handle)
        return True


def _should_start_background_services_during_import() -> bool:
    """Return whether import-time startup should bootstrap background services."""
    if __name__ == "__main__":
        return False

    process_name = Path(sys.argv[0]).name.casefold()
    if "pytest" in process_name:
        return False

    if os.getenv("FLASK_RUN_FROM_CLI") != "true":
        return True

    flask_args = [arg.casefold() for arg in sys.argv[1:]]
    if "run" not in flask_args:
        return False

    debug_enabled = (os.getenv("FLASK_DEBUG") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    } or "--debug" in flask_args
    return not (debug_enabled and os.getenv("WERKZEUG_RUN_MAIN") != "true")


@app.before_request
def ensure_runtime_schema() -> None:
    """Ensure runtime schema before handling non-static requests."""
    if request.endpoint == "static" or app.extensions.get("runtime_schema_checked"):
        return

    _ensure_runtime_schema()


@app.cli.command("sync-anesthesia-stop-times")
@click.option(
    "--start-date",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start work date in YYYY-MM-DD format.",
)
@click.option(
    "--end-date",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End work date in YYYY-MM-DD format.",
)
@click.option(
    "--overwrite-existing",
    is_flag=True,
    help="Replace existing anesthesia stop times instead of only filling blanks.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview matching updates without writing to the database.",
)
def sync_anesthesia_stop_times_command(
    start_date, end_date, overwrite_existing: bool, dry_run: bool
) -> None:
    """Sync anesthesia stop times from MSSQL into time-entry records."""
    result = None
    try:
        _ensure_runtime_schema()
        result = sync_anesthesia_stop_times(
            start_date=start_date.date(),
            end_date=end_date.date(),
            overwrite_existing=overwrite_existing,
            dry_run=dry_run,
            user=get_current_user(),
        )
    except AnesthesiaSyncError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(result.summary())


@app.cli.command("import-residents-csv")
@click.option(
    "--path",
    "csv_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the residents CSV bootstrap file.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate and preview resident changes without writing to the database.",
)
def import_residents_csv_command(csv_path: Path, dry_run: bool) -> None:
    """Import residents from a managed CSV file."""
    _ensure_runtime_schema()
    try:
        result = import_residents_csv_file(
            csv_path,
            user=get_current_user(),
            dry_run=dry_run,
        )
    except APIError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(result.summary())


def init_db():
    """Initialize database with default roles"""
    with app.app_context():
        _ensure_runtime_schema()

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


@app.cli.command("bootstrap-application")
@click.option(
    "--residents-csv",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional residents CSV file to import after schema/default bootstrap.",
)
def bootstrap_application_command(residents_csv: Path | None) -> None:
    """Bootstrap schema, defaults, and optionally residents from CSV."""
    init_db()
    click.echo("Schema and default data bootstrapped.")

    if residents_csv is None:
        return

    try:
        result = import_residents_csv_file(
            residents_csv,
            user=get_current_user(),
            dry_run=False,
        )
    except APIError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(result.summary())


if _should_start_background_services_during_import():
    start_background_services()


if __name__ == "__main__":
    import os

    init_db()
    start_background_services()
    # Always use debug=False for security
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=False, host="0.0.0.0", port=port)
