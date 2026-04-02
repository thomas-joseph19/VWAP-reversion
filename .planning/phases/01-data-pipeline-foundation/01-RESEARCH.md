# Phase 1: Data Pipeline Foundation - Research

**Researched:** 2026-04-02
**Domain:** Historical futures data ingestion, normalization, session labeling, and Parquet caching
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Front-month detection
- **D-01:** Determine the active NQ contract per trading day using same-day traded volume aggregated by outright contract symbol only, never nearest-expiry rules.
- **D-02:** Use a no-look-ahead daily mapping: each day selects the contract with the highest completed-day trade volume, and that mapping is the only contract exposed for that day's normalized dataset.
- **D-03:** Treat quarterly roll transitions as an explicit daily contract-map artifact so downstream phases can audit when the active symbol changed and handle discontinuities intentionally instead of blending contracts silently.

### Session and calendar labeling
- **D-04:** Convert all timestamps with `zoneinfo` to `America/New_York` and treat this as the canonical analysis timezone for every downstream dataset.
- **D-05:** Define the trading day by the Globex evening boundary: rows from 18:00 ET through the following 16:59:59 ET belong to the same trading date, with the 17:00-17:59 maintenance window excluded from session buckets.
- **D-06:** Emit row-level labels for `trading_date`, `session_name` (`overnight`, `rth`, `maintenance`), and boolean session flags so later phases can filter without recomputing calendar logic.

### Cache and file layout
- **D-07:** Build one canonical normalized parquet cache as the phase-1 source of truth rather than multiple partially overlapping datasets.
- **D-08:** Store parquet output partitioned by `trading_date` so reprocessing, spot validation, and partial reloads stay cheap while still supporting whole-history scans.
- **D-09:** Keep auxiliary artifacts alongside the canonical cache: a contract-roll map, schema summary, and data-quality report files for auditability.

### Data quality policy
- **D-10:** Fail fast on structural issues that would invalidate research output: missing required columns, unreadable files, timestamp parse failures, or inability to determine a front-month contract for a day.
- **D-11:** Tolerate recoverable row-level issues by dropping the affected rows and recording counts plus examples in a quality report; do not let a handful of bad rows abort the full historical build.
- **D-12:** Detect and report missing trading days, missing intraday intervals, and holiday/early-close anomalies explicitly, but preserve the available data unless the gap makes the day unusable under a documented threshold chosen during planning.

### Claude's Discretion
- Exact parquet engine and compression choice.
- Specific quality thresholds for declaring a day unusable.
- Internal module boundaries, function names, and report formatting.

### Deferred Ideas (OUT OF SCOPE)
None - discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | System ingests CME Globex MDP3 BBO 1-second CSV files | Use Polars lazy CSV scanning with explicit schema and a deterministic file manifest over the 884 local CSVs. |
| DATA-02 | System identifies front-month NQ contract using volume-based detection | Build a daily outright-only volume map from same-day trade rows, then persist a daily roll-map artifact. |
| DATA-03 | System handles quarterly contract rolls with price gap management | Keep rolls explicit by day, never stitch prices across contracts silently, and expose the contract symbol on every row. |
| DATA-04 | System converts timestamps from UTC to US/Eastern with correct DST handling | Use `zoneinfo.ZoneInfo("America/New_York")` and declare `tzdata` as a dependency for Windows. |
| DATA-05 | System defines session boundaries | Label `trading_date`, `session_name`, and boolean session flags from ET-local timestamps using the 18:00 Globex boundary. |
| DATA-06 | System performs one-time CSV→Parquet conversion and caches results | Write a single canonical Parquet dataset partitioned by `trading_date`, with PyArrow-backed partitioned writes. |
| DATA-07 | System validates data schema on load and reports quality issues | Separate structural failures from recoverable bad rows; emit schema summary plus a quality report with counts and examples. |
| DATA-08 | System detects data gaps and market holidays | Produce day-level and interval-level gap checks, distinguishing expected market closures from suspicious missing data. |
</phase_requirements>

## Summary

Phase 1 should be planned as a deterministic ETL build, not as ad hoc notebook logic. The phase output is one canonical, session-aware, front-month NQ dataset plus explicit audit artifacts. That means the planner should optimize for reproducibility, causal contract selection, and inspectable quality reporting before optimizing downstream indicator speed.

The main implementation choice is straightforward: use Polars for CSV scanning, filtering, grouping, and Parquet output; use `zoneinfo` with `tzdata` for timezone correctness on Windows; keep raw CSVs as source-of-truth and build a partitioned Parquet cache as the only normalized dataset. The raw feed sample in this workspace confirms important quirks the plan must account for: spread symbols are mixed into each file, `side='N'` rows can have blank `ts_event` and blank `price`, and spread rows can contain negative quoted prices. Those are not edge cases; they are first-order pipeline rules.

**Primary recommendation:** Plan Phase 1 as a four-artifact build: canonical Parquet dataset, daily contract-roll map, schema summary, and data-quality report, all derived from an explicit manifest of the 884 local CSV files.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14.3 local runtime | Pipeline runtime | Present locally now, and the current scientific stack supports it. |
| Polars | 1.39.3 current; 1.39.2 installed locally | CSV scan, filtering, grouping, Parquet writes | Best fit for lazy scans, typed ingestion, and fast columnar transforms. |
| PyArrow | 23.0.1 | Parquet engine and partitioned dataset writes | Current release, installed locally, and integrates directly with Polars. |
| NumPy | 2.4.4 | Gap analysis helpers, interval checks, light numeric work | Current release, installed locally, and standard for array operations. |
| `zoneinfo` | stdlib | Canonical timezone conversion | Official Python timezone path; required by the locked decisions. |
| `tzdata` | 2025.3 | IANA timezone data on Windows | Python docs recommend it for Windows targets without system tzdata. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Unit and integration tests | Add in Wave 0; no test framework exists in repo yet. |
| Numba | 0.64.0 | Later hot-loop acceleration | Keep in the project stack, but Phase 1 does not need it. |
| pathlib / json / logging | stdlib | Paths, artifacts, diagnostics | Use for manifesting inputs and writing audit outputs. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Polars | pandas | Simpler for many developers, but worse for lazy scans and large-file throughput. |
| PyArrow-backed partitioned Parquet dataset | Single monolithic Parquet file | Simpler to write once, but worse for targeted reprocessing and day-level validation. |
| `zoneinfo` + `tzdata` | `pytz` | Legacy path with no upside for a new Python 3.14 codebase. |

**Installation:**
```bash
python -m pip install polars pyarrow numpy tzdata pytest
```

**Version verification:** Verified on 2026-04-02 from PyPI and local environment.
- `polars` 1.39.3 released 2026-03-20; local install is 1.39.2, which was yanked.
- `pyarrow` 23.0.1 released 2026-02-16.
- `numpy` 2.4.4 released 2026-03-29.
- `pytest` 9.0.2 released 2025-12-06.
- `tzdata` 2025.3 released 2025-12-13.

## Architecture Patterns

### Recommended Project Structure
```text
src/
├── vwap_revert/
│   ├── data_pipeline/
│   │   ├── manifest.py      # discover and order raw CSV files
│   │   ├── schema.py        # required columns and dtypes
│   │   ├── ingest.py        # lazy CSV scan and outright filtering
│   │   ├── contracts.py     # same-day volume map and roll artifact
│   │   ├── sessions.py      # UTC→ET conversion and session labels
│   │   ├── quality.py       # gap checks and quality report generation
│   │   └── cache.py         # partitioned parquet writes and reads
│   └── cli.py               # build / inspect commands
tests/
└── data_pipeline/
```

### Pattern 1: Two-pass causal contract resolution
**What:** First pass builds a day→contract map from same-day outright trade volume; second pass filters each day to only the mapped contract.
**When to use:** Always. This is the project’s locked front-month policy.
**Example:**
```python
import polars as pl

TRADES = pl.col("side").is_in(["A", "B"])
OUTRIGHT = pl.col("symbol").str.starts_with("NQ") & ~pl.col("symbol").str.contains("-")

trade_volume = (
    pl.scan_csv(csv_path, schema=RAW_SCHEMA)
    .filter(OUTRIGHT & TRADES)
    .with_columns(
        pl.col("ts_recv").str.to_datetime(time_unit="ns", time_zone="UTC").alias("ts_utc")
    )
    .group_by(["trading_date", "symbol"])
    .agg(pl.col("size").sum().alias("trade_volume"))
)

front_month_map = (
    trade_volume
    .sort(["trading_date", "trade_volume", "symbol"], descending=[False, True, False])
    .group_by("trading_date")
    .first()
)
```

### Pattern 2: Session labels are derived once and stored
**What:** Convert to ET once, then derive `trading_date`, `session_name`, and boolean flags as persisted columns.
**When to use:** Immediately after contract filtering, before any quality or cache writes.
**Example:**
```python
from datetime import time, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

def trading_date_for(ts_et):
    t = ts_et.timetz().replace(tzinfo=None)
    if t >= time(18, 0):
        return (ts_et + timedelta(days=1)).date()
    return ts_et.date()
```

### Pattern 3: Canonical cache is a partitioned dataset, not ad hoc files
**What:** Write one normalized dataset partitioned by `trading_date`, plus sibling audit artifacts.
**When to use:** After a full successful build, and for partial rebuilds of affected dates.
**Example:**
```python
normalized_df.write_parquet(
    cache_dir,
    use_pyarrow=True,
    pyarrow_options={"partition_cols": ["trading_date"]},
    compression="zstd",
)
```

### Anti-Patterns to Avoid
- **Single-pass “pick front month while streaming rows”:** Violates the locked same-day completed-volume rule.
- **Treating spread rows as bad data after price-range checks:** Spread symbols are expected; filter them out before outright validation.
- **Using `ts_event` as the only timestamp anchor:** The local feed sample contains blank `ts_event` values on `side='N'` rows.
- **Recomputing session logic downstream:** Creates DST and maintenance-window drift.
- **Multiple “normalized” caches for different consumers:** Conflicts with the locked single canonical cache decision.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Columnar storage format | Custom binary cache | Parquet via PyArrow | Mature, inspectable, fast, and partition-friendly. |
| Timezone rules | Manual DST tables | `zoneinfo` + `tzdata` | Official IANA rules; avoids US DST edge bugs. |
| Large CSV parsing | Python `csv` loops | Polars lazy scan | Typed, parallel, and materially faster at this file count. |
| Partition discovery | Folder conventions only | Parquet dataset partition columns | Standard layout, easy partial reloads, and query pushdown. |

**Key insight:** The hard part of this phase is domain policy, not low-level file mechanics. Use standard storage and timezone tooling so planning effort stays focused on contract mapping, session semantics, and quality thresholds.

## Common Pitfalls

### Pitfall 1: Blank trade fields on non-trade rows
**What goes wrong:** The pipeline treats blank `price` or blank `ts_event` as fatal corruption.
**Why it happens:** In the sampled raw feed, `side='N'` rows are quote snapshots and can have null `price` and null `ts_event`.
**How to avoid:** Make field validation conditional on row type. Structural checks should require timestamps from the chosen canonical timestamp column, not from both raw timestamp columns.
**Warning signs:** Large “corrupt row” counts concentrated on `side='N'`.

### Pitfall 2: Spread contamination in outright logic
**What goes wrong:** Spread symbols distort front-month detection and price sanity checks.
**Why it happens:** Each file mixes outrights and spreads; sampled spread rows include symbols like `NQH1-NQZ1` and negative quoted spread prices.
**How to avoid:** Filter to outright `NQ` symbols before volume aggregation and price-range validation.
**Warning signs:** Front-month map chooses spread symbols or quality reports flag many “negative prices.”

### Pitfall 3: Wrong daily boundary
**What goes wrong:** Overnight rows are assigned to calendar date instead of Globex trading date.
**Why it happens:** Equities-style midnight boundaries are applied to futures data.
**How to avoid:** Compute `trading_date` from ET-local timestamps using the locked 18:00 boundary and explicit maintenance window.
**Warning signs:** RTH rows and preceding overnight rows land on different `trading_date` values.

### Pitfall 4: Hidden yanked dependency version
**What goes wrong:** Planning assumes “installed equals good,” but local `polars` is 1.39.2 and that release was yanked.
**Why it happens:** Environment and registry drift.
**How to avoid:** Plan an environment bootstrap step that upgrades `polars` before implementation.
**Warning signs:** Local environment differs from the verified version table.

### Pitfall 5: Overly vague unusable-day thresholds
**What goes wrong:** Quality reports exist, but planners cannot decide when a day blocks downstream work.
**Why it happens:** “Report gaps” is specified, but the operational threshold is left implicit.
**How to avoid:** Lock thresholds during planning. Recommended starting point: fail a day if no front-month mapping exists, if RTH has zero rows, or if any RTH gap exceeds 300 consecutive seconds; otherwise keep the day and report the issue.
**Warning signs:** Same data issue is sometimes treated as fatal and sometimes tolerated.

## Code Examples

Verified patterns from official sources:

### Lazy CSV scan with explicit filtering
```python
import polars as pl

OUTRIGHT = pl.col("symbol").str.starts_with("NQ") & ~pl.col("symbol").str.contains("-")

lf = (
    pl.scan_csv(csv_path, schema=RAW_SCHEMA)
    .filter(OUTRIGHT)
    .select(REQUIRED_COLUMNS)
)
```

### ET conversion with official timezone support
```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

ts_et = datetime.fromtimestamp(epoch_ns / 1_000_000_000, tz=timezone.utc).astimezone(NY)
```

### Partitioned Parquet write for canonical cache
```python
normalized_df.write_parquet(
    output_dir,
    use_pyarrow=True,
    pyarrow_options={"partition_cols": ["trading_date"]},
    compression="zstd",
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pytz` timezone handling | `zoneinfo` + `tzdata` | Python 3.9+ | Simpler, standard-library timezone logic with proper Windows story. |
| Eager pandas CSV ingestion | Polars lazy scans | Current ecosystem standard for large local columnar ETL | Better throughput and lower memory pressure. |
| One big cache file | Partitioned Parquet dataset | Current columnar analytics norm | Cheap day-level rebuilds and validation. |
| Expiry-date roll heuristics | Explicit same-day volume roll map | Project-locked current approach | Causal front-month selection with auditable roll dates. |

**Deprecated/outdated:**
- `pytz`: obsolete for this codebase.
- Nearest-expiry front-month rules: explicitly out of bounds for this phase.
- Silent continuous-contract stitching: conflicts with the explicit roll-map requirement.

## Open Questions

1. **Which raw timestamp becomes canonical inside the normalized dataset?**
   - What we know: `ts_recv` is always present in the sample; `ts_event` can be blank on non-trade rows.
   - What's unclear: Whether downstream analysis should preserve both raw timestamps and which one should drive gap analysis.
   - Recommendation: Store both, but use parsed `ts_recv` as the structural ordering key for Phase 1 unless a later validation proves `ts_event` is complete enough for all row classes.

2. **What exact unusable-day threshold should planning lock?**
   - What we know: Structural issues must fail fast; isolated bad rows should be tolerated.
   - What's unclear: The precise RTH gap and row-coverage threshold the planner should encode.
   - Recommendation: Start with `max_rth_gap_seconds=300` and `min_rth_coverage_pct=80`; revisit only if real data inspection shows too many false positives.

3. **Should cache writes upgrade local Polars first?**
   - What we know: Local `polars` is 1.39.2, and PyPI shows that release is yanked.
   - What's unclear: Whether implementation should proceed with the installed version or include an upgrade step.
   - Recommendation: Plan an explicit environment bootstrap task to move to `polars==1.39.3` before productionizing the cache build.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Raw CME/Databento CSV dataset | DATA-01 through DATA-08 | ✓ | 884 files present | — |
| Python | All implementation | ✓ | 3.14.3 | — |
| polars | Ingestion/cache build | ✓ | 1.39.2 local | Upgrade to 1.39.3 |
| pyarrow | Partitioned Parquet writes | ✓ | 23.0.1 | Use Polars native Parquet only if partitioned writes block |
| numpy | Gap checks/helpers | ✓ | 2.4.4 | stdlib for minimal checks |
| tzdata | Windows timezone support | ✓ | 2025.3 | None on Windows |
| pytest | Validation framework | ✗ | — | `unittest` smoke tests only, but weaker |

**Missing dependencies with no fallback:**
- None.

**Missing dependencies with fallback:**
- `pytest` is missing. Fallback is temporary `unittest`, but the planner should prefer installing `pytest` in Wave 0.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 9.0.2 |
| Config file | none - add in Wave 0 |
| Quick run command | `python -m pytest tests/data_pipeline/test_sessions.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Manifest and ingest the daily CSV shape correctly | integration | `python -m pytest tests/data_pipeline/test_ingest.py::test_reads_sample_day -x` | ❌ Wave 0 |
| DATA-02 | Select daily front-month by same-day outright trade volume | unit | `python -m pytest tests/data_pipeline/test_contracts.py::test_front_month_selected_by_daily_volume -x` | ❌ Wave 0 |
| DATA-03 | Emit explicit roll-map and preserve contract discontinuity | integration | `python -m pytest tests/data_pipeline/test_contracts.py::test_roll_map_records_symbol_changes -x` | ❌ Wave 0 |
| DATA-04 | Convert UTC timestamps to ET with DST correctness | unit | `python -m pytest tests/data_pipeline/test_sessions.py::test_dst_transition_dates -x` | ❌ Wave 0 |
| DATA-05 | Label `trading_date`, session name, and session flags correctly | unit | `python -m pytest tests/data_pipeline/test_sessions.py::test_globex_boundary_labels -x` | ❌ Wave 0 |
| DATA-06 | Build canonical partitioned Parquet cache | integration | `python -m pytest tests/data_pipeline/test_cache.py::test_partitioned_cache_layout -x` | ❌ Wave 0 |
| DATA-07 | Fail structural issues and report recoverable bad rows | unit | `python -m pytest tests/data_pipeline/test_quality.py::test_structural_vs_recoverable_errors -x` | ❌ Wave 0 |
| DATA-08 | Detect missing days, intraday gaps, and expected closures | unit | `python -m pytest tests/data_pipeline/test_quality.py::test_gap_detection_and_holiday_reporting -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/data_pipeline/test_sessions.py -x`
- **Per wave merge:** `python -m pytest tests/data_pipeline -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pytest` install step: `python -m pip install pytest`
- [ ] `tests/data_pipeline/test_ingest.py` - covers DATA-01
- [ ] `tests/data_pipeline/test_contracts.py` - covers DATA-02 and DATA-03
- [ ] `tests/data_pipeline/test_sessions.py` - covers DATA-04 and DATA-05
- [ ] `tests/data_pipeline/test_cache.py` - covers DATA-06
- [ ] `tests/data_pipeline/test_quality.py` - covers DATA-07 and DATA-08
- [ ] `pytest.ini` or `pyproject.toml` test config - test discovery and markers

## Sources

### Primary (HIGH confidence)
- Repository context: `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/PROJECT.md`
- Python docs: https://docs.python.org/3.14/library/zoneinfo.html
- Polars PyPI: https://pypi.org/project/polars/
- Polars docs reference: https://docs.pola.rs/docs/python/dev/reference/dataframe/index.html
- PyArrow PyPI: https://pypi.org/project/pyarrow/
- NumPy PyPI: https://pypi.org/project/numpy/
- pytest PyPI: https://pypi.org/project/pytest/
- tzdata PyPI: https://pypi.org/project/tzdata/

### Secondary (MEDIUM confidence)
- CME product page for NQ market context: https://www.cmegroup.com/markets/equities/nasdaq.html

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - official docs and package registry, plus local environment verification.
- Architecture: HIGH - strongly constrained by locked decisions and the observed raw data shape.
- Pitfalls: HIGH - directly supported by project decisions, local file inspection, and official timezone/storage docs.

**Research date:** 2026-04-02
**Valid until:** 2026-05-02
