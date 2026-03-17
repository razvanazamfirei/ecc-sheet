"""Helpers for optional SAML-based authentication."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from flask import current_app, has_app_context, request, session, url_for

from .env_utils import env_flag, env_str

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SESSION_USER_KEY = "auth_user"
_SESSION_DATA_KEY = "saml_authn"
_LOGIN_REQUEST_ID_KEY = "saml_request_id"
_LOGOUT_REQUEST_ID_KEY = "saml_logout_request_id"
_PUBLIC_ENDPOINTS = frozenset(
    {"auth.login", "auth.acs", "auth.sls", "auth.logout", "auth.metadata"}
)


class SAMLConfigError(RuntimeError):
    """Base exception for SAML configuration problems."""


class SAMLMissingDependencyError(SAMLConfigError):
    """Raised when the python3-saml library is not installed."""


class SAMLSettingsNotFoundError(SAMLConfigError):
    """Raised when no SAML settings source is provided or the file is missing."""


class SAMLInvalidJSONError(SAMLConfigError):
    """Raised when a SAML settings source contains malformed JSON."""


class SAMLInvalidSettingsError(SAMLConfigError):
    """Raised when SAML settings parse successfully but are not a JSON object."""


def saml_enabled(config: Mapping[str, object] | None = None) -> bool:
    """Return True when first-party SAML SSO is enabled."""
    if config is not None:
        return bool(config.get("SAML_ENABLED"))
    if has_app_context():
        return bool(current_app.config.get("SAML_ENABLED"))
    return env_flag("SAML_ENABLED")


def saml_public_endpoint(endpoint: str | None) -> bool:
    """Return True when an endpoint must stay reachable pre-auth."""
    return bool(endpoint) and endpoint in _PUBLIC_ENDPOINTS


def saml_logout_enabled(config: Mapping[str, object] | None = None) -> bool:
    """Return True when the loaded IdP config exposes a logout endpoint."""
    settings, _ = load_saml_settings(config=config)
    try:
        single_logout = settings.get("idp", {}).get("singleLogoutService", {})
    except AttributeError:
        return False
    return bool(single_logout.get("url"))


def get_session_authenticated_user() -> str:
    """Return the authenticated SAML session user or an empty string."""
    try:
        value = str(session.get(_SESSION_USER_KEY, "")).strip()
    except RuntimeError:
        return ""
    return value


def set_session_authenticated_user(
    username: str,
    *,
    name_id: str | None = None,
    session_index: str | None = None,
) -> None:
    """Persist authenticated SAML identity data in the Flask session."""
    normalized_username = str(username).strip()
    if not normalized_username:
        raise ValueError("username must be non-empty")

    session[_SESSION_USER_KEY] = normalized_username

    data: dict[str, Any] = {}
    if name_id:
        data["name_id"] = str(name_id).strip()
    if session_index:
        data["session_index"] = str(session_index).strip()
    session[_SESSION_DATA_KEY] = data
    session.permanent = True


def clear_session_authenticated_user() -> None:
    """Remove local SAML session state."""
    for key in (
        _SESSION_USER_KEY,
        _SESSION_DATA_KEY,
        _LOGIN_REQUEST_ID_KEY,
        _LOGOUT_REQUEST_ID_KEY,
    ):
        session.pop(key, None)


def get_saml_name_id() -> str | None:
    """Return the stored SAML NameID, if any."""
    try:
        data = session.get(_SESSION_DATA_KEY) or {}
    except RuntimeError:
        return None
    value = str(data.get("name_id", "")).strip()
    return value or None


def get_saml_session_index() -> str | None:
    """Return the stored SAML SessionIndex, if any."""
    try:
        data = session.get(_SESSION_DATA_KEY) or {}
    except RuntimeError:
        return None
    value = str(data.get("session_index", "")).strip()
    return value or None


def store_login_request_id(request_id: str | None) -> None:
    """Persist the last outbound AuthNRequest ID for ACS validation."""
    if request_id:
        session[_LOGIN_REQUEST_ID_KEY] = request_id
    else:
        session.pop(_LOGIN_REQUEST_ID_KEY, None)


def pop_login_request_id() -> str | None:
    """Return and remove the last outbound AuthNRequest ID."""
    value = session.pop(_LOGIN_REQUEST_ID_KEY, None)
    if value is None:
        return None
    return str(value).strip() or None


def store_logout_request_id(request_id: str | None) -> None:
    """Persist the last outbound LogoutRequest ID for SLS validation."""
    if request_id:
        session[_LOGOUT_REQUEST_ID_KEY] = request_id
    else:
        session.pop(_LOGOUT_REQUEST_ID_KEY, None)


def pop_logout_request_id() -> str | None:
    """Return and remove the last outbound LogoutRequest ID."""
    value = session.pop(_LOGOUT_REQUEST_ID_KEY, None)
    if value is None:
        return None
    return str(value).strip() or None


def get_saml_username_attributes(
    config: Mapping[str, object] | None = None,
) -> list[str]:
    """Return the ordered attribute names used to resolve the app username."""
    if config is not None:
        raw_value = config.get("SAML_USERNAME_ATTRIBUTES", [])
    elif has_app_context():
        raw_value = current_app.config.get("SAML_USERNAME_ATTRIBUTES", [])
    else:
        raw_value = []

    raw_items = raw_value.split(",") if isinstance(raw_value, str) else raw_value
    return [str(item).strip() for item in raw_items if str(item).strip()]


def saml_use_name_id(config: Mapping[str, object] | None = None) -> bool:
    """Return whether NameID can be used as a username fallback."""
    if config is not None:
        return bool(config.get("SAML_USE_NAME_ID", True))
    if has_app_context():
        return bool(current_app.config.get("SAML_USE_NAME_ID", True))
    return env_flag("SAML_USE_NAME_ID", default=True)


def load_saml_settings(
    config: Mapping[str, object] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Load the configured OneLogin toolkit settings."""
    if config is None and has_app_context():
        config = current_app.config

    settings_json = None
    settings_path_value = None
    if config is not None:
        settings_json = config.get("SAML_SETTINGS_JSON")
        settings_path_value = config.get("SAML_SETTINGS_PATH")
    else:
        settings_json = env_str("SAML_SETTINGS_JSON")
        settings_path_value = env_str("SAML_SETTINGS_PATH")

    if settings_json:
        try:
            settings = json.loads(str(settings_json))
        except json.JSONDecodeError as exc:
            raise SAMLInvalidJSONError("SAML_SETTINGS_JSON is not valid JSON.") from exc
        if not isinstance(settings, dict):
            raise SAMLInvalidSettingsError(
                "SAML_SETTINGS_JSON must decode to a JSON object."
            )
        return settings, None

    if not settings_path_value:
        raise SAMLSettingsNotFoundError(
            "SAML is enabled but no SAML settings were configured. "
            "Set SAML_SETTINGS_PATH or SAML_SETTINGS_JSON."
        )

    path = Path(str(settings_path_value))
    if not path.is_absolute():
        path = (_PROJECT_ROOT / path).resolve()
    if not path.is_file():
        raise SAMLSettingsNotFoundError(f"SAML settings file not found: {path}")

    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SAMLInvalidJSONError(
            f"SAML settings file is not valid JSON: {path}"
        ) from exc

    if not isinstance(settings, dict):
        raise SAMLInvalidSettingsError(
            f"SAML settings file must contain a JSON object: {path}"
        )

    return settings, str(path.parent)


def validate_saml_configuration(
    config: Mapping[str, object] | None = None,
) -> None:
    """Validate the SAML toolkit import and settings at startup.

    Raises SAMLConfigError if the dependency is missing or settings are
    misconfigured so the failure surfaces at startup rather than on the first
    request to /auth/login or /auth/metadata.
    """
    _import_saml_toolkit()
    load_saml_settings(config=config)


def build_saml_auth(flask_request):
    """Construct a OneLogin auth object for the current Flask request."""
    auth_class, _ = _import_saml_toolkit()
    settings, base_path = load_saml_settings()
    return auth_class(
        prepare_saml_request(flask_request),
        old_settings=settings,
        custom_base_path=base_path,
    )


def build_saml_settings():
    """Construct a OneLogin settings object for metadata generation."""
    _, settings_class = _import_saml_toolkit()
    settings, base_path = load_saml_settings()
    return settings_class(
        settings=settings,
        custom_base_path=base_path,
        sp_validation_only=True,
    )


def prepare_saml_request(flask_request) -> dict[str, Any]:
    """Map Flask request data to the structure expected by python3-saml."""
    forwarded_host = _forwarded_value(flask_request.headers.get("X-Forwarded-Host"))
    forwarded_proto = _forwarded_value(flask_request.headers.get("X-Forwarded-Proto"))
    forwarded_port = _forwarded_value(flask_request.headers.get("X-Forwarded-Port"))

    scheme = (forwarded_proto or flask_request.scheme or "http").lower()
    host = forwarded_host or flask_request.host
    port = forwarded_port or str(
        flask_request.environ.get("SERVER_PORT") or (443 if scheme == "https" else 80)
    )

    return {
        "http_host": host,
        "server_port": port,
        "script_name": flask_request.path,
        "get_data": flask_request.args.copy(),
        "post_data": flask_request.form.copy(),
        "query_string": flask_request.query_string,
        "request_uri": flask_request.full_path.rstrip("?"),
        "https": "on" if scheme == "https" else "off",
        "validate_signature_from_qs": True,
    }


def resolve_post_auth_redirect(target: str | None) -> str:
    """Return a safe post-auth redirect target."""
    fallback = default_post_auth_redirect()
    normalized = str(target or "").strip()
    if not normalized:
        return fallback

    parsed = urlsplit(normalized)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return fallback

    if not parsed.netloc:
        is_safe_local = normalized.startswith("/") and parsed.path not in {
            url_for("auth.acs"),
            url_for("auth.sls"),
        }
        return normalized if is_safe_local else fallback

    allowed_hosts: set[str] = {request.host}

    server_name = str(current_app.config.get("SERVER_NAME") or "").strip()
    if server_name:
        allowed_hosts.add(server_name)

    extra_hosts = current_app.config.get("SAML_ALLOWED_REDIRECT_HOSTS") or ()
    for host in extra_hosts:
        normalized_host = str(host or "").strip()
        if normalized_host:
            allowed_hosts.add(normalized_host)

    is_safe_host = parsed.netloc in allowed_hosts
    is_safe_path = parsed.path not in {url_for("auth.acs"), url_for("auth.sls")}
    return normalized if is_safe_host and is_safe_path else fallback


def default_post_auth_redirect() -> str:
    """Return the configured post-auth landing path."""
    configured = str(current_app.config.get("SAML_DEFAULT_NEXT_URL") or "").strip()
    if configured.startswith("/"):
        return configured
    return url_for("sheets.index")


def resolve_username(
    *,
    attributes: Mapping[str, list[str]] | None,
    name_id: str | None,
    config: Mapping[str, object] | None = None,
) -> str:
    """Resolve the application username from SAML attributes / NameID."""
    for attribute_name in get_saml_username_attributes(config=config):
        values = (attributes or {}).get(attribute_name) or []
        for value in values:
            normalized = str(value).strip()
            if normalized:
                return normalized

    if saml_use_name_id(config=config):
        normalized_name_id = str(name_id or "").strip()
        if normalized_name_id:
            return normalized_name_id

    return ""


def _forwarded_value(value: str | None) -> str:
    """Return the first normalized forwarded-header value."""
    if not value:
        return ""
    return value.split(",", 1)[0].strip()


def _import_saml_toolkit():
    """Import the optional python3-saml dependency."""
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth  # noqa: PLC0415
        from onelogin.saml2.settings import OneLogin_Saml2_Settings  # noqa: PLC0415
    except ImportError as exc:
        raise SAMLMissingDependencyError(
            "SAML is enabled but the optional python3-saml dependency is not "
            "installed. Run `uv sync --extra saml` after installing xmlsec."
        ) from exc

    return OneLogin_Saml2_Auth, OneLogin_Saml2_Settings
