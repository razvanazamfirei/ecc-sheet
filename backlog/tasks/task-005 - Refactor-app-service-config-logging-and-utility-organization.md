---
id: TASK-005
title: 'Refactor app service, config, logging, and utility organization'
status: Done
assignee: []
created_date: '2026-06-03 12:40'
updated_date: '2026-06-03 12:53'
labels:
  - refactor
dependencies: []
modified_files:
  - README.md
  - backend/anesthesia_sync.py
  - backend/app.py
  - backend/audit.py
  - backend/auth.py
  - backend/background_services.py
  - backend/config.py
  - backend/env_utils.py
  - backend/instance_config.py
  - backend/models.py
  - backend/resident_csv_import.py
  - backend/resident_normalization.py
  - backend/routes/schedule.py
  - backend/runtime_schema.py
  - backend/saml.py
  - backend/staff_import.py
  - backend/utils.py
  - docs/ARCHITECTURE.md
  - docs/schemas/instance-settings.schema.json
  - tests/test_app_init.py
  - tests/test_audit.py
  - tests/test_env_utils.py
  - tests/test_instance_config.py
priority: medium
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Refactor the Flask app organization without changing app architecture or behavior: move the background service out of app.py and gate it behind configuration, consolidate log_action/log_action_strict into one log_action(strict=...), move utility/name/env helpers into appropriate utility/config modules, and merge/document config and instance config handling.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Background service logic no longer lives in app.py and starts only when enabled by configuration.
- [x] #2 log_action and log_action_strict are collapsed into one log_action API with a strict argument, and call sites are updated.
- [x] #3 Utility, environment, cleaning, and name-parsing helpers are moved out of app.py into utility/config modules with imports kept readable.
- [x] #4 Config and instance config loading are merged consistently, documented, and preserve existing behavior.
- [x] #5 Relevant tests or validation commands pass.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Move the anesthesia auto-sync worker lifecycle out of backend/app.py into a dedicated backend/background_services.py module. Keep small backend.app wrappers for existing imports while the implementation accepts the Flask app and runtime-schema callback explicitly.
2. Merge env parsing and instance_settings.json role configuration into backend/config.py. Export the existing role constants from config.py, leave backend/instance_config.py as a compatibility shim, and update first-party imports to use backend.config.
3. Move cleaning/name/class-year helpers into backend/utils.py. Leave backend/resident_normalization.py as a compatibility shim, and reuse generic name-key helpers from utils in backend/anesthesia_sync.py.
4. Replace log_action_strict with log_action(..., strict=True), update strict convenience wrappers and tests, and remove first-party imports of log_action_strict.
5. Update README/docs where config/module organization is documented, then run focused pytest for config, audit, app init, env utilities, imports, and anesthesia sync.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented the requested refactor with backend.config as the canonical source for env parsing and instance role settings. Added backend.background_services for anesthesia auto-sync lifecycle and backend.runtime_schema for schema bootstrap helpers. Kept compatibility shims for backend.env_utils, backend.instance_config, and backend.resident_normalization while updating first-party imports to the new locations. backend/instance_settings.json had a pre-existing worktree diff and was intentionally left untouched.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Summary:
- Moved anesthesia auto-sync background service lifecycle into backend/background_services.py and kept backend.app wrappers for existing entry points; service startup still requires ANESTHESIA_FETCHER_ENABLED and skips testing/debug child-process cases as before.
- Moved runtime schema helpers into backend/runtime_schema.py, merged env parsing and instance_settings.json role loading into backend/config.py, and added get_flask_config() to merge both sources into Flask config.
- Collapsed audit logging to log_action(..., strict=True) and updated strict convenience wrappers/tests.
- Moved cleaning/name/class-year helpers into backend/utils.py, reused generic name matching in anesthesia sync, and left compatibility shims for old helper modules.
- Updated README and architecture docs for the new organization.

Validation:
- rtk uv run ruff check backend tests
- rtk uv run pytest tests

Notes:
- backend/instance_settings.json was already modified before this work and was not changed as part of this task.
<!-- SECTION:FINAL_SUMMARY:END -->
