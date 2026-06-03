#!/usr/bin/env python3
"""
Main entry point for the ECC Sheet application
Starts the Flask app with proper configuration
"""

from backend.app import app
from backend.background_services import start_background_services
from backend.database.bootstrap import init_db
from backend.database.runtime_schema import ensure_runtime_schema


def _ensure_runtime_schema() -> None:
    """Ensure runtime schema for the configured app."""
    ensure_runtime_schema(app, logger=app.logger)


if __name__ == "__main__":
    # Run the Flask app
    # Debug mode is disabled for production safety
    # Use host="0.0.0.0" to allow external connections if needed
    # Port can be configured via PORT environment variable in .env
    init_db(app, ensure_runtime_schema=_ensure_runtime_schema)
    start_background_services(app, _ensure_runtime_schema)
    app.run(debug=False, host="0.0.0.0", port=app.config.get("PORT", 5000))
