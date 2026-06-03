---
id: TASK-004
title: Simplify duplicate and over-abstracted code
status: Done
assignee: []
created_date: '2026-06-02 22:09'
updated_date: '2026-06-02 22:20'
labels:
  - cleanup
  - refactor
dependencies: []
modified_files:
  - backend/audit.py
  - backend/errors.py
  - backend/resident_csv_import.py
  - backend/routes/sheets.py
  - backend/utils.py
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reduce code duplication and unnecessary indirection in the current application while preserving public behavior, routes, data formats, templates, user-facing text, and existing architecture.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Existing test suite or equivalent checks run before changes, or absence of tests is documented.
- [x] #2 Duplicated or dead code is removed only where behavior can be preserved safely.
- [x] #3 Single-use pass-through helpers or wrappers are inlined when they obscure intent and are not public API.
- [x] #4 No broad architecture rewrite, new dependency, or unrelated formatting is introduced.
- [x] #5 Relevant tests, type checks, linters, or smoke checks pass after each focused cleanup batch.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Revised implementation plan after user direction to focus on Python code:
1. Preserve unrelated dirty work and avoid reverting existing local changes unless the user explicitly asks.
2. Inspect Python modules for duplicated helpers, pass-through wrappers, unused imports, and repeated logic using targeted static searches.
3. Prefer small behavior-preserving Python cleanups that can be validated despite the current pytest collection blocker.
4. Run focused Python static checks and any targeted tests that can execute; document existing blockers separately.
5. Keep frontend simplifications already made, but prioritize Python for the remaining work.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Python cleanup completed without broad architecture changes. Kept public exception classes, public audit functions, routes, response formats, and user-facing messages stable. Removed single-use wrappers in resident CSV import and sheet date parsing. Consolidated repeated fixed-status API exception constructors and audit payload/action assembly. Split backup_database file operations out of the broad try block so backend Ruff passes. Full Python tests and backend Ruff pass. ty check backend still reports 7 pre-existing diagnostics in app.py, report_utils.py, routes/_helpers.py, routes/entries.py, and saml.py; not expanded as part of this cleanup.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Simplified Python backend code without changing public behavior. Removed two private pass-through wrappers, consolidated repeated API error subclass constructors behind one fixed-status base, de-duplicated audit update/lock payload assembly, and split database backup work into focused helpers so backup_database no longer has an oversized try block. Validation: full pytest suite passes, backend Ruff passes, targeted module tests pass, frontend tests/build/format checks pass. The configured ty backend check still reports existing diagnostics outside this cleanup scope.
<!-- SECTION:FINAL_SUMMARY:END -->
