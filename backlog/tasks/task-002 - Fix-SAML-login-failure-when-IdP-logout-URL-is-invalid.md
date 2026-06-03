---
id: TASK-002
title: Fix SAML login failure when IdP logout URL is invalid
status: Done
assignee:
  - Codex
created_date: '2026-06-02 19:40'
updated_date: '2026-06-02 19:47'
labels:
  - bugfix
  - saml
  - auth
dependencies: []
references:
  - backend/saml.py
  - backend/routes/sso.py
  - tests/test_sso_routes.py
modified_files:
  - backend/saml.py
  - tests/test_sso_routes.py
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SAML-enabled login currently returns HTTP 500 before redirecting to the IdP when the python3-saml settings validator rejects an invalid or placeholder IdP singleLogoutService URL. The login flow should tolerate absent or unusable IdP logout configuration when logout is not required for login, while preserving local/session logout behavior and SAML metadata validation where appropriate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /auth/login redirects to the IdP instead of returning HTTP 500 when the loaded IdP singleLogoutService URL is blank, placeholder, or otherwise invalid but login settings are valid.
- [x] #2 SAML logout availability only reports true when the IdP singleLogoutService URL is present and valid enough for the SAML toolkit.
- [x] #3 Existing SAML login, ACS, local logout fallback, and metadata behavior remain covered by tests.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect backend/saml.py and existing SSO route tests to identify where settings are loaded, validated, and used for login/logout.
2. Add a small normalization/validation step that removes invalid IdP singleLogoutService URLs from loaded settings so login can initialize with valid SSO settings while saml_logout_enabled remains false for unusable SLO config.
3. Add focused regression tests for invalid/placeholder/blank SLO URL behavior and run targeted SAML tests plus relevant config/app startup tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented SAML settings normalization so invalid or blank optional IdP singleLogoutService.url values are removed before python3-saml settings objects are built. This keeps login usable while making saml_logout_enabled false for unusable SLO config. Added a real build_saml_auth login regression test plus logout availability tests for invalid, blank, and valid IdP SLO URLs. Verified full pytest passes; modified-file Ruff passes. Full Ruff still reports unrelated existing lint debt in other files.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed SAML settings loading to normalize the optional IdP singleLogoutService URL: valid toolkit-accepted URLs are preserved, whitespace is trimmed, and invalid or blank values are removed before python3-saml validates the settings. This prevents /auth/login from returning HTTP 500 for idp_slo_url_invalid while keeping SP-initiated logout disabled when the IdP SLO URL is unusable.

Added regression coverage that exercises the real login path with an invalid IdP SLO URL, plus direct logout availability tests for invalid, blank, and valid SLO settings. Cleaned the SSO route tests to use monkeypatch for app config restoration.

Verification: `rtk uv run pytest` passed with 636 tests; `rtk uv run ruff check backend/saml.py tests/test_sso_routes.py` passed. Full `rtk uv run ruff check` still reports unrelated existing lint failures outside this task.
<!-- SECTION:FINAL_SUMMARY:END -->
