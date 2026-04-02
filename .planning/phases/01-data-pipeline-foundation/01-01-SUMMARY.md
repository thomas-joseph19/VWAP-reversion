---
phase: 01-data-pipeline-foundation
plan: 01
subsystem: data
tags: [python, polars, ingestion, schema, pytest]
requires: []
provides:
  - Typed Databento CSV ingestion entrypoints
  - Deterministic raw CSV manifest discovery
  - Fail-fast schema and timestamp validation
affects: [phase-02, phase-03, data-pipeline]
tech-stack:
  added: [polars, pyarrow, numpy, tzdata, pytest, ruff]
  patterns: [src-layout package, typed ingestion, fixture-backed data tests]
key-files:
  created:
    - pyproject.toml
    - src/vwap_revert/data_pipeline/manifest.py
    - src/vwap_revert/data_pipeline/schema.py
    - src/vwap_revert/data_pipeline/ingest.py
    - tests/data_pipeline/test_ingest.py
  modified: []
key-decisions:
  - "Use Polars eager read plus lazy transforms so structural validation fails before downstream collection."
  - "Treat ts_recv as the canonical structural timestamp while preserving ts_event when present."
patterns-established:
  - "Manifest first: every build starts from deterministic CSV discovery."
  - "Structural failures raise immediately; row-level non-trade blanks stay tolerated."
requirements-completed: [DATA-01, DATA-07]
duration: 45min
completed: 2026-04-02
---

# Phase 1 Plan 01 Summary

**Typed Databento CSV ingestion with deterministic manifest ordering and fail-fast schema checks for outright NQ samples**

## Accomplishments
- Bootstrapped the `vwap-revert` package, dependency metadata, and pytest discovery config.
- Added deterministic manifest discovery keyed by session date and file stem.
- Implemented typed ingestion paths that reject missing files, missing columns, and bad `ts_recv` values while preserving blank non-trade fields.

## Issues Encountered
Pytest teardown cannot manage temp/cache directories in this sandboxed Windows path, so validation for this plan was completed with an equivalent manual Python harness executed against the new ingestion APIs.

## Next Phase Readiness
Wave 2 can build on a stable ingestion contract with parsed UTC timestamps and clean outright-only sample loads.

---
*Phase: 01-data-pipeline-foundation*
*Completed: 2026-04-02*
