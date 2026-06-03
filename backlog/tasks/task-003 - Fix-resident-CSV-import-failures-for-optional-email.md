---
id: TASK-003
title: Fix resident CSV import failures for optional email
status: Done
assignee:
  - Codex
created_date: '2026-06-02 21:44'
updated_date: '2026-06-02 21:45'
labels:
  - bug
  - tests
dependencies: []
modified_files:
  - backend/resident_csv_import.py
  - tests/test_resident_csv_import.py
priority: medium
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Resident CSV parsing should continue to allow omitted or blank optional email values while still rejecting non-blank invalid email values. The current parser raises before import conflict and audit tests can exercise their intended behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CSV rows with no email column parse with email set to null.
- [x] #2 CSV rows with a blank email value parse with email set to null.
- [x] #3 CSV rows with a non-blank invalid email value still raise a validation error.
- [x] #4 The full pytest suite passes.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Update resident CSV email normalization so omitted or blank email values are treated as optional and become null.
2. Add parser tests for missing email column and blank email value, while keeping the invalid non-blank email test intact.
3. Run focused resident CSV tests, then the full pytest suite, and check off acceptance criteria as they pass.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Focused resident CSV tests pass: `rtk uv run pytest tests/test_resident_csv_import.py` (15 passed). Missing email and blank email now parse as null; non-blank invalid email still raises.

Full pytest now passes: `rtk uv run pytest` (633 passed, 7 warnings). Modified-file Ruff and diff whitespace checks also pass: `rtk uv run ruff check backend/resident_csv_import.py tests/test_resident_csv_import.py`; `rtk git diff --check -- backend/resident_csv_import.py tests/test_resident_csv_import.py`.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Resident CSV email handling now treats omitted and blank email values as optional instead of passing an empty string into strict email validation. Added parser regression coverage for both missing email columns and blank email cells while retaining the existing invalid non-blank email validation behavior.

Verification:
- `rtk uv run pytest tests/test_resident_csv_import.py` (15 passed)
- `rtk uv run pytest` (633 passed, 7 warnings)
- `rtk uv run ruff check backend/resident_csv_import.py tests/test_resident_csv_import.py`
- `rtk git diff --check -- backend/resident_csv_import.py tests/test_resident_csv_import.py`
<!-- SECTION:FINAL_SUMMARY:END -->
