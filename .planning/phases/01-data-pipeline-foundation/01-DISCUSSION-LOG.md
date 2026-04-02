# Phase 1: Data Pipeline Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-02T08:15:23-04:00
**Phase:** 01-data-pipeline-foundation
**Areas discussed:** Front-month detection, Session and calendar labeling, Cache and file layout, Data quality policy

---

## Front-month detection

| Option | Description | Selected |
|--------|-------------|----------|
| Agent baseline | Use same-day outright trade volume to select the active front-month contract without look-ahead. | yes |
| Nearest expiry | Use contract calendar rules to infer front month. | |
| Hybrid/manual overrides | Use volume plus hard-coded roll dates or override files. | |

**User's choice:** Agent discretion - "whatever you think best"
**Notes:** Locked to the agent baseline because it aligns with DATA-02, avoids look-ahead bias, and keeps roll handling auditable.

---

## Session and calendar labeling

| Option | Description | Selected |
|--------|-------------|----------|
| Agent baseline | Canonical Eastern timestamps, Globex trading-date assignment, and row-level session labels. | yes |
| Calendar-day labels | Assign rows by midnight-to-midnight local calendar dates. | |
| Derived-only sessions | Keep raw timestamps only and let later phases infer sessions. | |

**User's choice:** Agent discretion - "same for 2"
**Notes:** Chosen to make DST handling and later session filters deterministic across all downstream phases.

---

## Cache and file layout

| Option | Description | Selected |
|--------|-------------|----------|
| Agent baseline | One canonical parquet cache partitioned by trading date plus supporting audit artifacts. | yes |
| Multiple specialized datasets | Separate caches for sessions, contracts, and analytics views. | |
| No persistent cache | Recompute from CSV each time. | |

**User's choice:** Agent discretion - "same for 3"
**Notes:** Selected for simplicity, reproducibility, and fast downstream reuse.

---

## Data quality policy

| Option | Description | Selected |
|--------|-------------|----------|
| Agent baseline | Fail on structural corruption, tolerate isolated bad rows with reporting, surface gaps explicitly. | yes |
| Strict abort | Abort the build on any row-level issue. | |
| Best effort only | Keep processing with minimal validation. | |

**User's choice:** Agent discretion - "same for 4"
**Notes:** Balanced toward research integrity without making the historical build brittle.

---

## the agent's Discretion

- The user delegated all four gray areas to the agent.
- Exact implementation details remain flexible within the decisions recorded in CONTEXT.md.

## Deferred Ideas

None.
