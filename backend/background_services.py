"""Background service lifecycle management."""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import TextIO

from flask import Flask

from backend.anesthesia_sync import sync_anesthesia_stop_times
from backend.config import Config, env_flag, env_str
from backend.utils import get_effective_date

try:
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - exercised in import-safe tests
    fcntl = None

logger = logging.getLogger(__name__)
_background_sync_lock = threading.Lock()

type RuntimeSchemaCallback = Callable[[], None]


def _auto_sync_lookback_days(app: Flask) -> int:
    """Return the configured automatic sync lookback, clamped non-negative."""
    return max(
        0,
        int(
            app.config.get(
                "ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS",
                Config.ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS,
            )
        ),
    )


def _auto_sync_interval_seconds(app: Flask) -> int:
    """Return the configured automatic sync interval, clamped to 300s minimum."""
    return max(
        300,
        int(
            app.config.get(
                "ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS",
                Config.ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS,
            )
        ),
    )


def _auto_sync_window(app: Flask) -> tuple[date, date]:
    """Return the rolling date window for automatic anesthesia stop syncing."""
    effective_date = get_effective_date()
    return effective_date - timedelta(
        days=_auto_sync_lookback_days(app)
    ), effective_date


def _run_auto_anesthesia_sync_once(
    app: Flask,
    ensure_runtime_schema: RuntimeSchemaCallback,
) -> None:
    """Run one automatic anesthesia stop-time sync cycle."""
    with app.app_context():
        ensure_runtime_schema()
        start_date, end_date = _auto_sync_window(app)
        result = sync_anesthesia_stop_times(
            start_date=start_date,
            end_date=end_date,
            overwrite_existing=False,
            dry_run=False,
            user="anesthesia-auto-sync",
        )
        logger.info("Automatic anesthesia stop-time sync: %s", result.summary())


def _auto_anesthesia_sync_loop(
    app: Flask,
    ensure_runtime_schema: RuntimeSchemaCallback,
    stop_event: threading.Event,
) -> None:
    """Run automatic anesthesia stop-time sync on a fixed interval."""
    try:
        interval_seconds = _auto_sync_interval_seconds(app)
        lookback_days = _auto_sync_lookback_days(app)
    except (TypeError, ValueError):
        logger.exception("Invalid anesthesia auto-sync configuration")
        return
    logger.info(
        "Automatic anesthesia stop-time sync started (interval=%ss, lookback_days=%s).",
        interval_seconds,
        lookback_days,
    )
    while not stop_event.is_set():
        try:
            _run_auto_anesthesia_sync_once(app, ensure_runtime_schema)
        except Exception:
            logger.exception("Automatic anesthesia stop-time sync failed")

        if stop_event.wait(interval_seconds):
            break


def _background_service_lock_path(app: Flask) -> Path:
    """Return the process-lock path for the anesthesia auto-sync worker."""
    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)
    return instance_dir / "anesthesia-auto-sync.lock"


def _acquire_background_service_process_lock(app: Flask) -> TextIO | None:
    """Acquire a cross-process lock so only one worker runs auto-sync."""
    lock_handle = _background_service_lock_path(app).open("a+", encoding="utf-8")
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


def background_services_enabled(app: Flask) -> bool:
    """Return whether automatic background services are enabled by config."""
    return bool(app.config.get("ANESTHESIA_FETCHER_ENABLED"))


def start_background_services(
    app: Flask,
    ensure_runtime_schema: RuntimeSchemaCallback,
) -> bool:
    """Start background services once for the deployment."""
    if app.config.get("TESTING"):
        return False
    if not background_services_enabled(app):
        return False
    if app.debug and env_str("WERKZEUG_RUN_MAIN") != "true":
        return False

    started = False
    with _background_sync_lock:
        existing_service = app.extensions.get("anesthesia_auto_sync_service")
        if existing_service is None:
            try:
                lock_handle = _acquire_background_service_process_lock(app)
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
                        args=(app, ensure_runtime_schema, stop_event),
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


def stop_background_services(app: Flask) -> bool:
    """Stop background services for the current process when running."""
    with _background_sync_lock:
        existing_service = app.extensions.get("anesthesia_auto_sync_service")
        if existing_service is None:
            return False

        stop_event = existing_service["stop_event"]
        worker = existing_service["thread"]
        lock_handle = existing_service.get("lock_handle")
        stop_event.set()
        while worker.is_alive():
            worker.join(timeout=1)
        _release_background_service_process_lock(lock_handle)
        app.extensions.pop("anesthesia_auto_sync_service", None)
        return True


def should_start_background_services_during_import(
    *,
    module_name: str,
    argv: Sequence[str] | None = None,
) -> bool:
    """Return whether import-time startup should bootstrap background services."""
    if module_name == "__main__":
        return False

    runtime_argv = sys.argv if argv is None else list(argv)
    process_name = Path(runtime_argv[0]).name.casefold() if runtime_argv else ""
    if "pytest" in process_name:
        return False

    if env_str("FLASK_RUN_FROM_CLI") != "true":
        return True

    flask_args = [arg.casefold() for arg in runtime_argv[1:]]
    if "run" not in flask_args:
        return False

    debug_enabled = env_flag("FLASK_DEBUG") or "--debug" in flask_args
    return not (debug_enabled and env_str("WERKZEUG_RUN_MAIN") != "true")
