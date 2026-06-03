"""Blueprint registration."""

from flask import Flask

from backend.routes import (
    api,
    audit,
    dev,
    entries,
    holidays,
    reports,
    residents,
    roles,
    schedule,
    sheets,
    sso,
)


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the app."""
    app.register_blueprint(sso.bp)
    app.register_blueprint(sheets.bp)
    app.register_blueprint(entries.bp)
    app.register_blueprint(schedule.bp)
    app.register_blueprint(residents.bp)
    app.register_blueprint(roles.bp)
    app.register_blueprint(holidays.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(audit.bp)
    app.register_blueprint(dev.bp)
