---
id: TASK-006
title: Consolidate backend module organization after config refactor
status: Done
assignee: []
created_date: '2026-06-03 12:56'
updated_date: '2026-06-03 13:10'
labels:
  - refactor
dependencies: []
priority: medium
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second refactor pass after TASK-005: remove compatibility wrapper modules and consolidate backend code into clearer feature/support modules without changing behavior. Move CLI commands out of app.py, group auth/SAML/reporting/import/database helpers where appropriate, and keep app.py focused on app construction, request hooks, and blueprint registration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Compatibility wrapper modules introduced during the first refactor are removed, and all first-party imports point to canonical modules.
- [x] #2 CLI commands no longer live directly in backend/app.py and are registered from a dedicated CLI module.
- [x] #3 Runtime database bootstrap/tasks and background-service concerns stay out of app.py with clear module boundaries.
- [x] #4 Auth/SAML, reporting, and import-related code is grouped more coherently where practical without changing route behavior.
- [x] #5 Docs/tests/import paths are updated and the full test suite plus lint pass.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove the temporary compatibility wrapper modules from TASK-005: backend/env_utils.py, backend/instance_config.py, and backend/resident_normalization.py. Verify no first-party imports depend on them.
2. Create focused backend packages: backend/security for auth and SAML plus Flask auth hook setup, backend/imports for staff and resident CSV imports, backend/reporting for report/payroll helpers, and backend/database for commit/session, runtime schema, and default-data bootstrap.
3. Move CLI command registration out of backend/app.py into backend/cli.py. Keep app.py focused on Flask app construction, extension setup, blueprint registration, security hook setup, runtime schema request hook, and background-service startup.
4. Update routes, models, tests, scripts, and docs to use the new canonical import paths. Avoid compatibility wrappers except package __init__ exports for canonical package APIs.
5. Run Ruff format/check and the full pytest suite; update Backlog acceptance criteria and final summary when complete.
<!-- SECTION:PLAN:END -->

## Notes

<!-- SECTION:NOTES:BEGIN -->
- Removed temporary compatibility modules and updated imports to canonical `backend.config`, `backend.utils`, `backend.security`, `backend.imports`, `backend.reporting`, and `backend.database` paths.
- Moved CLI registration to `backend/cli.py`, Flask auth/SAML hook setup to `backend/security/flask.py`, DB bootstrap/runtime schema code to `backend/database/`, and import/reporting helpers into focused packages.
- Validation: Ruff format/check completed; full test suite reported passing after the final import-path updates.
<!-- SECTION:NOTES:END -->
