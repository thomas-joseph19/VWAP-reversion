# Phase 07: Volume Profile Engine - Research

**Researched:** 2026-04-02
**Domain:** Completed-session volume profiles, HTF composite profiles, LVN detection, and row-aligned structural enrichment
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Profile session scope and causality
- **D-01:** Compute three distinct completed-session profile families from trade-bearing rows only: prior completed RTH daily profiles keyed by `trading_date`, same-day overnight profiles covering the Globex session from 18:00 ET through the 9:29:59 ET pre-open boundary, and a rolling HTF composite built from prior completed daily RTH profiles only.
- **D-02:** Preserve strict causality for every structural reference: rows on trading date `T` may use the overnight profile completed before that day's RTH open, the prior completed daily profile from `T-1`, and HTF composites built from completed sessions strictly earlier than `T`; same-session developing RTH profiles must not leak into the row-aligned features.
- **D-03:** Reuse the Phase 1 `trading_date`, `is_overnight`, and `is_rth` labels as the only session boundary source so DST handling, maintenance-window exclusion, and contract selection stay inherited rather than reimplemented in this phase.

### Price bucketing and level extraction
- **D-04:** Build histograms on a configurable price bucket size that defaults to one NQ tick (`0.25` points), snapping trade prices onto a deterministic tick grid so all emitted structural levels remain compatible with later trade simulation and chart validation.
- **D-05:** Keep the Phase 3 value-area definition for all completed profiles: `POC` is the highest-volume bucket with the same deterministic fair-value and lower-price tie breaks, and `VAH`/`VAL` expand contiguously to the 70% target using stable adjacent-volume tie breaks.
- **D-06:** Detect LVNs from completed profile histograms using a lightly smoothed local-minimum rule with deterministic prominence thresholds, favoring stable, repeatable nodes over ultra-sensitive single-bucket noise; expose the detected node prices as numeric references rather than only human-readable annotations.

### HTF composite structure and downstream features
- **D-07:** Define the HTF profile as a rolling 180-trading-day composite of completed daily RTH histograms, updated once per trading date without look-ahead bias and rebuilt deterministically from the canonical cache rather than incrementally mutating hidden state.
- **D-08:** Derive HTF balance-area extremes from the composite profile's completed value-area boundaries and publish the corresponding HTF `POC`, `VAH`, `VAL`, and LVN references so later phases can score structural confluence against both local and higher-timeframe context.
- **D-09:** Emit row-aligned Phase 7 features that forward-carry the active overnight, prior-day daily, and HTF structural references onto each canonical row, including numeric distances, nearest-level labels, and explicit quality/status fields so Phase 9 can swap in these richer levels without reshaping upstream data contracts.

### Artifact and validation surface
- **D-10:** Materialize profile outputs as deterministic parquet artifacts for each profile family plus a row-aligned enriched dataset, following the same CLI-driven rebuild pattern used in Phases 2 through 6.
- **D-11:** Produce manual validation exports that let the user compare selected sessions against external profile charts, with separate visibility into overnight value area, daily profile levels, HTF balance edges, and detected LVNs for each validation date.
- **D-12:** Preserve Phase 3 compatibility during the transition by keeping explicit prior-day structural columns available in the enriched Phase 7 output while adding the richer overnight/HTF references as new columns instead of replacing the baseline contract silently.

### Claude's Discretion
- Exact smoothing kernel and prominence thresholds for LVN detection, provided they remain deterministic, documented, and testable.
- Precise artifact filenames and module boundaries for histogram builders, composite-profile assembly, and validation-export helpers.
- Additional helper columns that improve auditability, such as profile bucket counts, source-session coverage, or composite window metadata.

### Deferred Ideas (OUT OF SCOPE)
- Developing same-session RTH volume-profile features belong to a later enhancement once the baseline completed-session structural engine is in place.
- Regime-aware structural thresholds and weekly/monthly VWAP confluence remain Phase 8 work.
- Continuation-failure logic and confluence-driven entry scoring remain Phase 9 work.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STRC-02 | System computes overnight value area edges (globex session before RTH) | Build a completed overnight histogram keyed by `trading_date`, compute deterministic `POC`/`VAH`/`VAL`, and forward-carry those levels onto same-day rows only after the overnight session is complete. |
| STRC-03 | System builds daily volume profiles (price × volume histogram at configurable tick resolution) | Build per-session histogram artifacts on a tick-aligned price grid from trade rows only, preserving bucket metadata and deterministic value-area derivation. |
| STRC-04 | System builds HTF volume profile (rolling 180-day composite) without look-ahead bias | Reuse completed daily RTH histograms as the primitive, then sum only prior-window histograms into one composite per `trading_date`. |
| STRC-05 | System identifies Low Volume Nodes (LVNs) from volume profiles | Apply a deterministic smoothed local-minimum rule to completed histograms and publish node prices plus provenance/quality metadata. |
| STRC-06 | System identifies balance area extremes from HTF volume profiles | Compute HTF `POC`/`VAH`/`VAL` from the completed 180-day composite and carry those balance edges into the enriched row-level artifact. |
</phase_requirements>

## Summary

Phase 07 should not invent a new subsystem. The repo already has the right implementation shape: consume the Phase 1 canonical cache, build deterministic per-session artifacts in an indicator module, emit validation exports with manifests, and expose one CLI rebuild command for the whole phase. The planning focus should be on causal profile boundaries, reusable artifact contracts, and stable row-level columns, not on framework selection.

The core implementation pattern is: first build completed-session histograms as explicit artifacts, then derive structural levels from those histograms, then join the active overnight, prior-day, and HTF references back onto the full canonical row stream. For the HTF profile, the planner should treat daily RTH histograms as the source primitive and compose the rolling 180-day window by summing aligned daily histograms, not by re-scanning raw rows inside every window.

The main unresolved planning risk is contract-roll discontinuity inside the 180-day HTF composite. Phase 1 explicitly preserved roll changes as auditable state instead of silently blending contracts. That means a raw-price 180-day histogram can span quarterly roll gaps unless the plan handles them intentionally. The planner needs to make that policy explicit instead of assuming the composite is automatically meaningful across all 180 sessions.

**Primary recommendation:** Implement Phase 07 as one new `volume_profile` indicator module and one `build-phase7-volume-profile` CLI command that write completed-session histogram artifacts first, derive deterministic overnight/daily/HTF levels second, and emit a Phase 3-compatible enriched parquet plus validation exports third.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `polars` | Repo pin `>=1.39.3,<1.40`; local env `1.39.2`; public PyPI page currently shows `1.38.1` uploaded 2026-02-06 | Session filtering, histogram aggregation, rolling joins, parquet artifacts | The repo is already Polars-first and the required `group_by`, `over`, parquet, and lazy scan patterns are already in production code. |
| `pyarrow` | Repo pin `>=23.0.1,<24`; local env `23.0.1`; PyPI `23.0.1` uploaded 2026-02-16 | Partitioned parquet writes and stable artifact IO | Phase 1 already depends on Arrow-backed parquet writes for the canonical cache. |
| `numpy` | Repo pin `>=2.4.4,<3`; local env `2.4.4`; public PyPI page currently shows `2.4.3` uploaded 2026-03-09 | Small dense-array helpers for histogram smoothing, LVN prominence math, and aligned composite summation | Useful for deterministic local-minimum detection without bringing in a heavier signal-processing dependency. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | Repo pin `>=9.0.2,<10`; local env `8.4.2`; PyPI `9.0.2` uploaded 2025-12-06 | Unit and CLI/artifact validation | Use `python -m pytest` for all planning commands in this workspace. |
| `ruff` | Repo pin `>=0.13,<0.14`; local package not verified for Phase 7 planning | Linting only | Optional; do not let lint-tool drift block the phase plan. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `numpy` smoothing helper for LVNs | `scipy.signal` peak/minimum helpers | Adds a new dependency for a small deterministic calculation the current stack can already cover. |
| Phase-local histogram artifacts + enriched parquet | Only a single enriched row-level dataset | Simpler surface, but loses the reusable HTF/daily histogram primitive the planner needs for causal validation. |
| Summed daily histograms for HTF | Re-bin raw rows for each 180-day window | Conceptually simple, but far more expensive and harder to audit for look-ahead errors. |

**Installation:**
```bash
python -m pip install -e .[dev]
```

**Version verification:**
- `pyarrow` latest public PyPI release visible to me is `23.0.1` uploaded 2026-02-16.
- `pytest` latest public PyPI release visible to me is `9.0.2` uploaded 2025-12-06.
- `polars` and `numpy` have contradictory public vs local metadata in this workspace: the local interpreter imports `polars 1.39.2` and `numpy 2.4.4`, while current public PyPI pages visible to me show `polars 1.38.1` and `numpy 2.4.3`. Treat local runnable versions as authoritative for planning unless dependency normalization is added explicitly.

## Architecture Patterns

### Recommended Project Structure
```text
src/
|-- vwap_revert/
|   |-- cli.py                               # Phase 7 command registration
|   |-- indicators/
|   |   |-- structural_levels.py             # Existing Phase 3 baseline
|   |   `-- volume_profile.py                # Phase 7 histogram + composite + enrichment logic
|   `-- data_pipeline/
|       |-- cache.py                         # Canonical cache reload
|       `-- sessions.py                      # Locked session labels
tests/
`-- indicators/
    |-- test_volume_profile.py               # histogram/value-area/LVN/composite logic
    `-- test_volume_profile_validation.py    # CLI and artifact validation
```

### Pattern 1: Build completed-session histograms as the source of truth
**What:** Produce one explicit artifact per profile family before any row-level join: overnight histograms keyed by current `trading_date`, daily RTH histograms keyed by completed `trading_date`, and HTF composite histograms keyed by the current date that consumes them.
**When to use:** Always. Structural levels should be derived from explicit histograms, not computed ad hoc inside row-enrichment code.
**Example:**
```python
trade_rows = df.filter(pl.col("side").is_in(["A", "B"]))

overnight_hist = (
    trade_rows.filter(pl.col("is_overnight"))
    .with_columns((pl.col("price") / bucket_size).round(0).mul(bucket_size).alias("bucket_price"))
    .group_by(["trading_date", "bucket_price"])
    .agg(pl.col("size").sum().alias("volume"))
    .sort(["trading_date", "bucket_price"])
)
```
Source: local Phase 3 histogram pattern plus locked Phase 7 decisions D-01 through D-05

### Pattern 2: Derive the HTF composite by summing aligned daily histograms
**What:** Treat each completed daily RTH histogram as a reusable vector on the shared tick grid, then build the 180-day composite by summing only prior-window histograms for each current date.
**When to use:** For every HTF artifact and every HTF-derived `POC`/`VAH`/`VAL`/LVN level.
**Example:**
```python
window_hist = pl.concat(window_daily_histograms, how="vertical_relaxed")
htf_hist = (
    window_hist.group_by("bucket_price")
    .agg(pl.col("volume").sum().alias("volume"))
    .sort("bucket_price")
)
```
Source: locked Phase 7 decision D-07 and the repo's artifact-first design

### Pattern 3: Keep level extraction in small deterministic helpers
**What:** Reuse the Phase 3 `POC` and value-area tie-break semantics in pure helpers, then add a second helper for LVN detection that smooths the histogram lightly and picks local minima using deterministic prominence rules.
**When to use:** Any step where dense Polars expressions would make the tie-break logic opaque or hard to test.
**Example:**
```python
smoothed = np.convolve(volumes, np.array([1.0, 2.0, 1.0]) / 4.0, mode="same")
is_lvn = (
    (smoothed[1:-1] < smoothed[:-2])
    & (smoothed[1:-1] < smoothed[2:])
    & ((np.minimum(smoothed[:-2], smoothed[2:]) - smoothed[1:-1]) >= min_prominence)
)
```
Source: project-locked Phase 7 discretion area for LVN smoothing/prominence; NumPy used as a deterministic scalar-array helper

### Pattern 4: Join active references back onto the full row stream without breaking Phase 3
**What:** Build one per-date summary table of active overnight, prior-day, and HTF levels, then left-join it to the canonical row stream while preserving existing `prior_rth_*` columns and nearest-level/proximity style columns.
**When to use:** For the enriched Phase 7 dataset consumed by later phases.
**Example:**
```python
base = df.with_row_index("__row")
enriched = base.join(active_levels, on="trading_date", how="left").sort("__row").drop("__row")
```
Source: [src/vwap_revert/indicators/structural_levels.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/structural_levels.py) and [src/vwap_revert/indicators/vwap.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/vwap.py)

### Anti-Patterns to Avoid
- **Same-session RTH leakage:** Do not expose developing current-day RTH profile levels to rows on that same date.
- **Inline histogram blobs in the enriched parquet:** Keep full histograms in dedicated artifacts; the enriched row-level file should carry only derived references and metadata.
- **Recomputing 180-day windows from raw rows in an inner loop:** Use daily histogram primitives and windowed summation instead.
- **Silently replacing Phase 3 columns:** Keep explicit `prior_rth_*` compatibility columns in the enriched output.
- **Assuming raw front-month prices are safe to blend across quarterly rolls:** Phase 1 explicitly preserved roll discontinuity; HTF handling must be intentional.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session boundary logic | New ET/day-boundary parser | Existing `label_sessions()` outputs from Phase 1 | DST, maintenance-hour exclusion, and overnight boundaries are already locked and tested. |
| Canonical data reload | New file-scanning layer | `scan_canonical_cache()` | Keeps Phase 7 on the trusted Phase 1 dataset boundary. |
| Phase 3 compatibility | One-off schema translation later | Preserve and extend the existing structural contract now | Later setup/trade phases already depend on `prior_rth_*`-style fields. |
| Validation artifact format | Notebook-only exports | Existing per-phase `validation/*.csv` + `validation_sessions.json` pattern | Matches Phases 2 through 6 and keeps manual review reproducible. |

**Key insight:** The difficult part of this phase is not histogram math. It is preserving causal boundaries, stable artifact contracts, and explicit handling of contract-roll discontinuity inside a long HTF window.

## Common Pitfalls

### Pitfall 1: Mis-scoping the overnight session
**What goes wrong:** Overnight value area uses midnight-to-open rows or leaks prior RTH rows into the overnight profile.
**Why it happens:** The overnight session crosses midnight and is easy to redefine accidentally.
**How to avoid:** Use only the Phase 1 `trading_date` plus `is_overnight` labels. Do not re-derive boundaries in Phase 7.
**Warning signs:** Overnight `source_trading_date` does not match the same-day RTH open, or overnight profile row counts spike around calendar boundaries.

### Pitfall 2: HTF look-ahead bias
**What goes wrong:** A row on date `T` sees a composite that includes date `T`'s own RTH distribution.
**Why it happens:** The planner joins same-day daily histograms into the HTF window instead of shifting them out.
**How to avoid:** Build HTF composites only from completed daily RTH histograms strictly earlier than the target date.
**Warning signs:** The first rows of a session already reflect same-day closing structure.

### Pitfall 3: LVN detection that is too sensitive to one bucket
**What goes wrong:** Every small dip becomes an LVN, causing unstable level sets and downstream confluence noise.
**Why it happens:** Raw tick histograms are noisy, especially with one-tick bins.
**How to avoid:** Smooth lightly first, require a deterministic prominence threshold, and test stability on hand-built fixtures.
**Warning signs:** LVN counts explode for similar sessions, or the detected nodes move materially when one bucket changes by a tiny amount.

### Pitfall 4: Blending quarterly roll gaps into the HTF profile
**What goes wrong:** The 180-day histogram contains multiple roll-step price regimes on the same raw axis, distorting `POC`, value area, and LVNs.
**Why it happens:** Phase 1 intentionally keeps roll discontinuities explicit rather than silently back-adjusting prices.
**How to avoid:** Add an explicit HTF roll policy to the plan and validate around real roll windows.
**Warning signs:** HTF histograms become bimodal near known roll periods or balance-area edges drift by roll premium rather than traded structure.

### Pitfall 5: Storing full profile structure only in row-level output
**What goes wrong:** Later phases cannot audit or recompute HTF logic without re-running the entire phase.
**Why it happens:** The plan optimizes for one convenient enriched parquet and skips reusable per-family artifacts.
**How to avoid:** Persist histogram/level artifacts per family and treat the enriched parquet as a derived convenience layer.
**Warning signs:** Validation exports need to reconstruct histograms from row-level columns.

### Pitfall 6: Version drift hiding reproducibility issues
**What goes wrong:** The plan assumes pinned dependency versions that are not actually what this workspace runs.
**Why it happens:** `pyproject.toml`, local imports, and public package metadata disagree.
**How to avoid:** Use `python -m pytest` in the validation commands and keep Phase 7 logic within APIs already exercised by earlier phases.
**Warning signs:** A command works locally but fails in a clean env, or public package metadata does not match repo pins.

## Code Examples

Verified patterns from local code and official docs:

### Window/join-back semantics for row-aligned indicators
```python
df.with_columns(
    pl.col("size").cum_sum().over("trading_date").alias("cum_volume")
)
```
Source: https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.over.html

### Partitioned parquet writing with PyArrow-backed partition columns
```python
df.write_parquet(
    output_dir,
    use_pyarrow=True,
    pyarrow_options={"partition_cols": ["trading_date"]},
)
```
Source: https://docs.pola.rs/py-polars/html/reference/api/polars.DataFrame.write_parquet.html

### Lazy reload of the canonical partitioned cache
```python
lf = pl.scan_parquet(cache_root, hive_partitioning=True)
```
Source: https://docs.pola.rs/api/python/stable/reference/api/polars.scan_parquet.html

### Existing repo pattern for deterministic validation exports
```python
comparison = (
    enriched_df.with_columns(pl.col("trading_date").cast(pl.Utf8))
    .filter(pl.col("trading_date").is_in(validation_dates))
    .sort(["trading_date", "ts_recv_et"])
)
comparison.write_csv(validation_dir / "structural_validation_export.csv")
```
Source: [src/vwap_revert/indicators/structural_levels.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/structural_levels.py)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prior-day RTH value-area proxy only | Completed overnight, prior-day, and prior-only HTF profile references | Locked for Phase 7 on 2026-04-02 | Later phases can score richer structural confluence without redesigning the data contract. |
| Structural levels derived directly from the prior session only | Histogram artifacts first, derived levels second, row-level enrichment third | Established by Phase 2-6 artifact pattern and reinforced in Phase 7 | Improves auditability and keeps expensive HTF computation reusable. |
| Manual chart annotations only | Numeric distances, nearest-level labels, quality fields, and validation exports | Ongoing repo pattern through Phase 6 | Makes the outputs usable for both rule-based signals and later analytics/ML work. |

**Deprecated/outdated:**
- Re-deriving session boundaries inside indicator modules instead of using Phase 1 labels.
- Treating HTF structure as presentation-only rather than a reusable numeric artifact.
- Replacing Phase 3 columns silently instead of extending the structural contract.

## Open Questions

1. **How should the HTF 180-day composite handle quarterly roll discontinuities?**
   - What we know: Phase 1 preserves roll changes explicitly and does not silently stitch contracts; the Phase 7 context says to rebuild from the canonical cache.
   - What's unclear: Whether the HTF histogram should use raw front-month prices, deterministic price adjustment, or a restricted same-contract window.
   - Recommendation: Make this an explicit planning task before implementation starts. At minimum, inspect `contract_roll_map.parquet` and validate composite shape across known roll windows before finalizing the HTF artifact contract.

2. **How many LVNs should the row-level artifact publish per family?**
   - What we know: The context requires numeric LVN references, but not a fixed cardinality.
   - What's unclear: Whether to publish nearest-above/nearest-below only, top-N by prominence, or a list-typed column.
   - Recommendation: Prefer explicit scalar columns for the nearest-above and nearest-below LVN per family, plus a profile-level artifact that preserves the full LVN set.

3. **Should HTF quality/status degrade when the composite window has fewer than 180 usable sessions?**
   - What we know: Early dates in the history cannot have a full 180-day lookback, and missing/unusable sessions already exist as explicit quality concepts in the repo.
   - What's unclear: Whether partial-window HTF levels should be published as usable with metadata or null until the full window exists.
   - Recommendation: Publish partial-window HTF levels with explicit `source_session_count` and a quality/status field; let downstream consumers decide whether to require full-window maturity.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Phase runtime and CLI | Yes | 3.14.3 | - |
| `polars` | Histogram aggregation and row enrichment | Yes | 1.39.2 | Keep to already-used APIs if version parity is not normalized. |
| `pyarrow` | Parquet artifact writing | Yes | 23.0.1 | - |
| `numpy` | LVN smoothing/helper math | Yes | 2.4.4 | Pure Python loops if necessary, though not recommended. |
| `python -m pytest` | Automated validation | Yes | 8.4.2 | - |
| `pytest` on `PATH` | Direct CLI convenience | No | - | Use `python -m pytest`. |

**Missing dependencies with no fallback:**
- None for planning.

**Missing dependencies with fallback:**
- Bare `pytest` is not on `PATH`; use `python -m pytest`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 8.4.2` installed locally; repo declares `pytest>=9.0.2,<10` |
| Config file | `pyproject.toml` |
| Quick run command | `python -m pytest tests/indicators/test_volume_profile.py -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STRC-02 | Overnight profile computes same-day `POC`/`VAH`/`VAL` from completed overnight trade rows only | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_overnight_profile_uses_completed_globex_rows_only -q` | No - Wave 0 |
| STRC-03 | Daily profile artifacts build deterministic tick-aligned histograms and Phase 3-compatible prior-day levels | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_daily_profiles_build_tick_aligned_histograms_and_prior_day_levels -q` | No - Wave 0 |
| STRC-04 | HTF composite uses only prior completed daily histograms and reports source-session coverage | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_htf_composite_excludes_current_session_and_tracks_window_coverage -q` | No - Wave 0 |
| STRC-05 | LVN detection uses deterministic smoothing/prominence rather than raw single-bucket minima | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_lvn_detection_prefers_stable_local_minima -q` | No - Wave 0 |
| STRC-06 | HTF `POC`/`VAH`/`VAL` become row-level balance-area references with explicit quality fields | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_enriched_output_carries_htf_balance_edges_and_quality_status -q` | No - Wave 0 |
| STRC-02, STRC-03, STRC-04, STRC-05, STRC-06 | CLI writes deterministic family artifacts, enriched parquet, validation CSV, and manifest | integration | `python -m pytest tests/indicators/test_volume_profile_validation.py -q` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/indicators/test_volume_profile.py -q`
- **Per wave merge:** `python -m pytest tests/indicators/test_volume_profile.py tests/indicators/test_volume_profile_validation.py -q`
- **Phase gate:** `python -m pytest -q`

### Wave 0 Gaps
- [ ] `tests/indicators/test_volume_profile.py` - deterministic unit coverage for overnight profiles, daily histogram construction, HTF causality, LVN detection, partial-window quality states, and Phase 3 compatibility.
- [ ] `tests/indicators/test_volume_profile_validation.py` - CLI and artifact coverage for all Phase 7 outputs and validation exports.
- [ ] Roll-window fixture data - explicit sample sessions around a quarterly roll to force an HTF composite policy test instead of leaving it implicit.
- [ ] Pytest cache warning mitigation - this workspace can run tests, but `pytest` warns that `.pytest_cache` cannot be created under the repo root.

## Sources

### Primary (HIGH confidence)
- Local context: `.planning/phases/07-volume-profile-engine/07-CONTEXT.md` - locked Phase 7 scope and implementation decisions
- Local context: `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - roll-discontinuity and session-label decisions that constrain HTF design
- Local code: [src/vwap_revert/indicators/structural_levels.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/structural_levels.py) - deterministic value-area logic and row-level structural pattern to preserve
- Local code: [src/vwap_revert/indicators/vwap.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/vwap.py) - validation-export and enriched-parquet pattern
- Local code: [src/vwap_revert/data_pipeline/sessions.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/data_pipeline/sessions.py) - canonical overnight/RTH session labels
- Local code: [src/vwap_revert/data_pipeline/contracts.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/data_pipeline/contracts.py) - explicit roll-map behavior and the fact that contract discontinuity is preserved, not silently blended
- Polars docs: https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.over.html - window/join-back semantics
- Polars docs: https://docs.pola.rs/api/python/stable/reference/api/polars.scan_parquet.html - `scan_parquet(..., hive_partitioning=True)` semantics
- Polars docs: https://docs.pola.rs/py-polars/html/reference/api/polars.DataFrame.write_parquet.html - PyArrow-backed partitioned parquet writing
- PyPI: https://pypi.org/project/pyarrow/ - current public `23.0.1` release metadata
- PyPI: https://pypi.org/project/pytest/ - current public `9.0.2` release metadata

### Secondary (MEDIUM confidence)
- PyPI: https://pypi.org/project/polars/ - current public metadata, which conflicts with the local installed version and repo pin
- PyPI: https://pypi.org/project/numpy/ - current public metadata, which conflicts with the local installed version and repo pin
- TradingView support concepts for volume profile terminology and 70% value area: https://www.tradingview.com/support/solutions/43000502040-volume-profile/?offer_id=10
- Local domain research: `.planning/research/PITFALLS.md` - useful risk framing for roll-gap handling and LVN/bin-size stability, but not a locked phase decision source

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - the repo stack is clear, but public package metadata currently conflicts with local runnable versions for `polars` and `numpy`
- Architecture: HIGH - the codebase already has a strong reusable pattern for deterministic artifact-producing phases
- Pitfalls: MEDIUM - most are clear from the repo and phase context, but HTF roll handling remains an unresolved design choice that must be made explicit during planning

**Research date:** 2026-04-02
**Valid until:** 2026-05-02
