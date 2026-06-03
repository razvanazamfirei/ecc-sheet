"""Flask integration for authentication and SAML security."""

from __future__ import annotations

import warnings as _warnings

from flask import Flask, jsonify, redirect, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import SQLAlchemyError

from backend.errors import SAMLConfigError
from backend.models import Resident
from backend.routes import dev as _dev_module
from backend.routes import sso as _sso_module
from backend.security.auth import (
    get_admin_users,
    get_current_user,
    get_payroll_admin_users,
    is_admin,
    mock_users_enabled,
)
from backend.security.saml import (
    get_session_authenticated_user,
    saml_enabled,
    saml_public_endpoint,
    validate_saml_configuration,
)
from backend.utils import wants_json_response


def _authentication_required_response(*, redirect_to_login: bool = False):
    """Return an auth challenge for missing identity."""
    message = "Authentication required."
    if redirect_to_login and not wants_json_response() and request.method == "GET":
        next_url = request.full_path.rstrip("?") or request.path
        return redirect(url_for("auth.login", next=next_url))
    if wants_json_response():
        return jsonify({"success": False, "message": message}), 401
    return message, 401


def _build_mock_personas() -> list[dict[str, str]]:
    """Return the available dev personas for the mock-user dropdown."""
    admin_users = get_admin_users()
    payroll_users = get_payroll_admin_users()

    personas = [{"name": admin_users[0] if admin_users else "Admin", "label": "Admin"}]
    if payroll_users:
        personas.append({"name": payroll_users[0], "label": "Payroll Admin"})
    personas.append({"name": "Regular Viewer", "label": "Regular Viewer"})
    return personas


def _active_resident_names(app: Flask) -> list[str]:
    """Return active resident names for the dev mock-user dropdown."""
    try:
        residents = Resident.query.filter_by(active=True).order_by(Resident.name).all()
    except SQLAlchemyError:
        app.logger.exception("Failed to query residents for dev mock context")
        return []

    return [resident.name for resident in residents]


def configure_security(app: Flask, csrf: CSRFProtect) -> None:
    """Configure auth startup checks, request guards, and template context."""
    csrf.exempt(_sso_module.bp)

    if saml_enabled(app.config):
        try:
            validate_saml_configuration(config=app.config)
        except SAMLConfigError as exc:
            raise RuntimeError(
                f"SAML startup check failed: {exc} — "
                "fix SAML settings or unset SAML_ENABLED."
            ) from exc

    if mock_users_enabled():
        if str(app.config.get("FLASK_ENV") or "").strip().lower() == "production":
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

    @app.context_processor
    def inject_auth():
        """Inject authentication functions into template context."""
        session_user = get_session_authenticated_user()
        has_mock_session = mock_users_enabled() and bool(session.get("dev_user"))
        return {
            "current_user": get_current_user(),
            "is_admin": is_admin(),
            "can_logout": bool(
                (session_user and saml_enabled(app.config)) or has_mock_session
            ),
        }

    @app.context_processor
    def inject_dev():
        """Inject dev mock-user context (only when MOCK_USERS_ENABLED is set)."""
        if not mock_users_enabled():
            return {"mock_users_enabled": False}

        return {
            "mock_users_enabled": True,
            "mock_personas": _build_mock_personas(),
            "mock_residents": _active_resident_names(app),
            "dev_user_override": session.get("dev_user"),
        }
