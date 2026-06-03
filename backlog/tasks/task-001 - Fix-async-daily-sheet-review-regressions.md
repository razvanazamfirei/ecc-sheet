---
id: TASK-001
title: Fix async daily sheet review regressions
status: Done
assignee: []
created_date: '2026-06-02 16:10'
updated_date: '2026-06-02 17:00'
labels:
  - bugfix
  - review-feedback
dependencies: []
modified_files:
  - backend/app.py
  - frontend/templates/base.html
  - tests/test_app_init.py
  - tests/test_auth.py
priority: medium
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Resolve the review-reported UI regressions in the async daily-sheet flows so normal browser use matches the declared server/template behavior. Keep the fixes scoped to the daily sheet JavaScript and dev-session menu template.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Unlocking an initially locked sheet restores visible add/edit/delete/import controls without a full page refresh.
- [x] #2 Async entry deletion still honors the existing confirmation dialog before sending the POST.
- [x] #3 Adding the first entry to an empty weekend or holiday sheet preserves the Start Time column/input context.
- [x] #4 Development session menu actions declared as POST-only submit POST forms instead of GET anchors.
- [x] #5 Focused tests or manual verification cover the affected flows.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect the daily sheet template and JavaScript helpers that render add-entry controls, entry rows, empty tables, and confirmation handling.
2. Update the async unlock path so missing edit controls can be restored after an initially locked render, using existing server-rendered markup or minimal DOM helpers without changing architecture.
3. Update async delete handling so the existing confirmation dialog runs before the async POST, while preserving JSON deletion and row removal after confirmation.
4. Preserve weekend/holiday context for empty async inserts by deriving it from durable page metadata rather than existing row cells only.
5. Replace POST-only dev menu anchors with POST forms consistent with the existing quick-persona pattern.
6. Run focused tests or, if no JS test harness exists, targeted template/static checks plus relevant app tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented review fixes in frontend/static/js/daily-sheet.js, frontend/templates/index.html, frontend/templates/base.html, and tests/test_auth.py. Verification passed: rtk vitest run; rtk run uv run pytest tests/test_auth.py tests/test_dev_routes.py; rtk run mise exec -- bun run format:check; rtk run mise exec -- bun run build.

Additional final verification passed: rtk run uv run pytest (629 passed, 3 existing SQLAlchemy delete warnings in entry-delete tests).

Follow-up fix: replaced the dev menu Become Admin gate from not is_admin to the dedicated can_escalate_to_admin context flag, sourced from auth.can_escalate_to_admin(). Added tests proving regular mock users do not see the action while the owner identity sees the POST form.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Follow-up: tightened the dev Become Admin menu so it uses the same can_escalate_to_admin capability as the POST route instead of showing the form to every non-admin. The global auth context now exposes can_escalate_to_admin, base.html gates the form on it, and tests cover both denied and allowed mock identities.
<!-- SECTION:FINAL_SUMMARY:END -->
