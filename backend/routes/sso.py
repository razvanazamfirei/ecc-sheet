"""First-party SAML SSO routes."""

from __future__ import annotations

from flask import Blueprint, Response, abort, current_app, redirect, request

from ..saml import (
    build_saml_auth,
    build_saml_settings,
    clear_session_authenticated_user,
    get_saml_name_id,
    get_saml_session_index,
    pop_login_request_id,
    pop_logout_request_id,
    resolve_post_auth_redirect,
    resolve_username,
    saml_enabled,
    saml_logout_enabled,
    set_session_authenticated_user,
    store_login_request_id,
    store_logout_request_id,
)

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _require_saml_enabled() -> None:
    if not saml_enabled():
        abort(404)


@bp.get("/login")
def login():
    """Start SP-initiated SAML login."""
    _require_saml_enabled()

    auth = build_saml_auth(request)
    target = resolve_post_auth_redirect(request.args.get("next"))
    redirect_url = auth.login(return_to=target)
    store_login_request_id(auth.get_last_request_id())
    return redirect(redirect_url)


@bp.post("/acs")
def acs():
    """Assertion Consumer Service endpoint."""
    _require_saml_enabled()

    auth = build_saml_auth(request)
    auth.process_response(request_id=pop_login_request_id())
    errors = auth.get_errors()
    if errors:
        current_app.logger.error(
            "SAML ACS failed: %s (%s)",
            ", ".join(errors),
            auth.get_last_error_reason(),
        )
        clear_session_authenticated_user()
        return "SAML authentication failed.", 400

    if not auth.is_authenticated():
        clear_session_authenticated_user()
        return "SAML authentication failed.", 401

    attributes = auth.get_attributes()
    name_id = auth.get_nameid()
    username = resolve_username(attributes=attributes, name_id=name_id)
    if not username:
        current_app.logger.error(
            "SAML ACS succeeded but no usable username was found. "
            "Configured attributes: %s",
            current_app.config.get("SAML_USERNAME_ATTRIBUTES"),
        )
        clear_session_authenticated_user()
        return "SAML response did not contain a usable username.", 400

    set_session_authenticated_user(
        username,
        name_id=name_id,
        session_index=auth.get_session_index(),
        attributes=attributes,
    )

    relay_state = request.form.get("RelayState")
    return redirect(resolve_post_auth_redirect(relay_state))


@bp.route("/sls", methods=["GET", "POST"])
def sls():
    """Single Logout Service endpoint."""
    _require_saml_enabled()

    auth = build_saml_auth(request)
    redirect_url = auth.process_slo(
        request_id=pop_logout_request_id(),
        delete_session_cb=clear_session_authenticated_user,
    )
    errors = auth.get_errors()
    if errors:
        current_app.logger.error(
            "SAML SLS failed: %s (%s)",
            ", ".join(errors),
            auth.get_last_error_reason(),
        )
        return "SAML logout failed.", 400

    if redirect_url:
        return redirect(resolve_post_auth_redirect(redirect_url))

    clear_session_authenticated_user()
    return redirect(resolve_post_auth_redirect(request.values.get("RelayState")))


@bp.get("/logout")
def logout():
    """Start SP-initiated logout when supported, otherwise clear local session."""
    _require_saml_enabled()

    target = resolve_post_auth_redirect(request.args.get("next"))
    if not saml_logout_enabled():
        clear_session_authenticated_user()
        return redirect(target)

    auth = build_saml_auth(request)
    redirect_url = auth.logout(
        return_to=target,
        name_id=get_saml_name_id(),
        session_index=get_saml_session_index(),
    )
    store_logout_request_id(auth.get_last_request_id())
    return redirect(redirect_url)


@bp.get("/metadata")
def metadata():
    """Expose SP metadata for IdP configuration."""
    _require_saml_enabled()

    saml_settings = build_saml_settings()
    metadata_xml = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata_xml)
    if errors:
        current_app.logger.error(
            "SAML metadata validation failed: %s",
            ", ".join(errors),
        )
        return "Invalid SAML metadata configuration.", 500

    return Response(metadata_xml, mimetype="application/samlmetadata+xml")
