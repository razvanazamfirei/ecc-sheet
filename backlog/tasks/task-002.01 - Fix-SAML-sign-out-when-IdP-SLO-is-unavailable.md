---
id: TASK-002.01
title: Fix SAML sign-out when IdP SLO is unavailable
status: Done
assignee:
  - Codex
created_date: '2026-06-02 21:08'
updated_date: '2026-06-02 21:11'
labels:
  - bugfix
  - saml
  - auth
dependencies: []
references:
  - backend/saml.py
  - backend/routes/sso.py
  - tests/test_sso_routes.py
  - docs/DEPLOYMENT.md
modified_files:
  - backend/config.py
  - backend/saml.py
  - backend/routes/sso.py
  - tests/test_sso_routes.py
  - docs/DEPLOYMENT.md
parent_task_id: TASK-002
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-002. SAML sign-out currently only performs IdP logout when the IdP singleLogoutService URL can be used as a true SAML SLO endpoint. When SLO is absent, invalid, or the deployment needs a provider-specific logout endpoint, /auth/logout clears the Flask session but redirects back into a protected route, allowing the still-active IdP session to immediately authenticate the user again. Add a clear local-session-first logout flow with a configurable IdP logout redirect fallback for deployments without working SAML SLO.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /auth/logout clears the local SAML session before any outbound IdP logout redirect.
- [x] #2 When SAML SLO is unavailable but a configured IdP logout URL is present and safe, /auth/logout redirects there after clearing the local session.
- [x] #3 When true SAML SLO is configured, existing SP-initiated SLO behavior remains intact and stores the logout request id.
- [x] #4 When neither SAML SLO nor fallback IdP logout URL is configured, /auth/logout still clears local session and redirects to the resolved local target.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a SAML_IDP_LOGOUT_URL config value and SAML helper functions to validate/build a safe fallback IdP logout redirect, preserving the local return target as RelayState/return_to when appropriate.
2. Update /auth/logout so local Flask SAML state is cleared before any outbound logout redirect; use true SAML SLO when available, otherwise redirect to the configured fallback IdP logout URL, otherwise return to the local target.
3. Add tests for fallback IdP logout, local-session-first behavior, unchanged true SAML SLO behavior, and local-only logout. Update deployment docs to explain why logout can appear to fail and how to configure the fallback.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented a separate SAML_IDP_LOGOUT_URL fallback for IdPs that do not provide working SAML SLO. /auth/logout now clears local SAML session state before redirecting out to either the configured provider logout URL or the SAML SLO redirect. The SAML SLO branch still stores saml_logout_request_id after clearing auth_user/saml_authn so SLS validation can continue without leaving the user locally authenticated. Added tests for provider logout fallback, invalid fallback rejection, true SLO request-id preservation, and local-only logout. Updated deployment docs to explain why logout can appear to immediately reauthenticate when the IdP session remains active.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed SAML sign-out behavior by separating generic provider logout from true SAML Single Logout. The app now supports `SAML_IDP_LOGOUT_URL` for IdPs that require a normal logout endpoint; when configured with an absolute http/https URL, `/auth/logout` clears the local Flask SAML session and redirects there. If the fallback is not configured, existing SAML SLO remains intact for valid IdP `singleLogoutService` settings, but now clears `auth_user`/`saml_authn` before sending the browser to the IdP while preserving `saml_logout_request_id` for SLS validation.

Updated SAML route/config tests and deployment docs. Verification: `rtk uv run pytest tests/test_sso_routes.py tests/test_config.py` passed with 32 tests; modified-file Ruff passed; full `rtk uv run pytest` passed with 639 tests. Full-project Ruff still has unrelated existing lint debt outside this task.
<!-- SECTION:FINAL_SUMMARY:END -->
