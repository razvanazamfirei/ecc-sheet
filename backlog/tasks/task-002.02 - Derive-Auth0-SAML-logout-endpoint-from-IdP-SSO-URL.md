---
id: TASK-002.02
title: Derive Auth0 SAML logout endpoint from IdP SSO URL
status: Done
assignee:
  - Codex
created_date: '2026-06-02 21:29'
updated_date: '2026-06-02 21:37'
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
  - backend/saml.py
  - tests/test_sso_routes.py
  - docs/DEPLOYMENT.md
parent_task_id: TASK-002
priority: high
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-002.01. For Auth0-style SAML applications, the IdP SSO URL is `https://{yourDomain}/samlp/{client_id}` and logout must send a SAML LogoutRequest to `https://{yourDomain}/samlp/{client_id}/logout`. Ensure the SAML settings normalization derives that SLO URL when the configured IdP SLO URL is missing, blank, or invalid, while preserving local session clearing and existing local-only fallback behavior for non-Auth0-shaped SSO URLs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When the IdP SSO URL is `https://{domain}/samlp/{client_id}` and IdP SLO is missing, blank, or invalid, /auth/logout sends the browser to `https://{domain}/samlp/{client_id}/logout` with a SAML LogoutRequest.
- [x] #2 /auth/logout clears local SAML session state while preserving the logout request id needed for SLS validation.
- [x] #3 If the IdP SSO URL does not have the `/samlp/{client_id}` shape and no valid SLO URL is configured, existing local-only fallback behavior remains intact.
- [x] #4 Deployment docs and example settings identify `https://{yourDomain}/samlp/{client_id}/logout` as the Auth0 SAML logout endpoint.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove the normalized-settings/deepcopy layer entirely.
2. Use `idp.singleSignOnService.url` as the single source for Auth0 SAML logout derivation inside `load_saml_settings`: when it is `https://{domain}/samlp/{client_id}`, set `idp.singleLogoutService.url` to the same URL plus `/logout` before handing settings to python3-saml.
3. Keep /auth/logout on python3-saml's normal logout flow and keep only focused tests/docs for that behavior.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reworked the logout change per feedback: removed SAML_IDP_LOGOUT_URL and the normalized-settings/deepcopy/helper approach. `load_saml_settings` now uses `idp.singleSignOnService.url` as the single source for Auth0-style SAML logout derivation: `/samlp/{client_id}` becomes `/samlp/{client_id}/logout` before python3-saml builds the LogoutRequest. /auth/logout remains on the normal python3-saml logout flow and clears local auth state before redirecting while preserving saml_logout_request_id. Focused SAML/config tests and modified-file Ruff pass. Full pytest was run but failed on unrelated dirty worktree changes in auth owner/admin tests and resident CSV import email parsing.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Simplified the Auth0 SAML logout fix around one source of truth: the IdP SSO URL. Removed the separate configured logout URL path and the normalized-settings/deepcopy helper. `load_saml_settings` now derives `idp.singleLogoutService.url` directly from `idp.singleSignOnService.url` when it has the Auth0 shape `https://{domain}/samlp/{client_id}`, producing `https://{domain}/samlp/{client_id}/logout`. `/auth/logout` then uses python3-saml's normal LogoutRequest flow, so the browser is sent to that endpoint with `SAMLRequest=...`.

Updated focused SAML route/settings tests and deployment docs. Verification: `rtk uv run pytest tests/test_sso_routes.py tests/test_config.py` passed with 33 tests; `rtk uv run ruff check backend/saml.py backend/routes/sso.py tests/test_sso_routes.py tests/test_config.py` passed; `rtk git diff --check` passed. Full `rtk uv run pytest` was attempted but currently fails on unrelated dirty-worktree changes outside SAML.
<!-- SECTION:FINAL_SUMMARY:END -->
