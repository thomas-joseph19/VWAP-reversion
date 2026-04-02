# Phase 03: Simple Structural Levels - Research

**Researched:** 2026-04-02
**Domain:** Prior-session RTH volume profile levels and row-aligned structural proximity features
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Session scope and source data
- **D-01:** Build prior-day value area levels from the prior completed RTH session only, not the full 24-hour session, so the structural references align with the strategy's RTH-only execution model and Phase 2's RTH-anchored VWAP baseline.
- **D-02:** Derive the prior-day profile from trade-bearing observations available in the 1-second BBO dataset, using actual traded volume distribution where Phase 1/2 data semantics identify trade prints; quote-only rows must not contribute synthetic volume to the value area.
- **D-03:** Treat the prior session as the most recent completed RTH session on the previous `trading_date`; if that session is missing or unusable, emit null structural levels plus explicit quality metadata instead of silently substituting another day.

### Profile construction and level definition
- **D-04:** Compute the prior-day profile on native traded price levels from the 1-second dataset rather than introducing wider custom buckets, preserving maximum information for future machine-learning feature extraction and avoiding irreversible aggregation choices in the baseline artifact.
- **D-05:** Define `POC` as the price level with the highest traded volume in the prior RTH session; when multiple prices tie, break ties deterministically by choosing the price closest to the session's volume-weighted fair-value center and then the lower price if still tied.
- **D-06:** Define `VAH` and `VAL` using a deterministic 70% value-area expansion around `POC`, expanding to the adjacent price level with greater incremental volume at each step and using a stable tie-break rule so outputs are reproducible and audit-friendly.

### Output shape and proximity features
- **D-07:** Publish a compact per-session structural-level artifact keyed by `trading_date` and also a row-aligned enriched dataset that forward-carries the active prior-day `VAH`, `VAL`, and `POC` onto each current-session row, matching the Phase 2 pattern of reusable downstream columns.
- **D-08:** Compute proximity using the current row's best available actionable price from the BBO dataset, with a configurable absolute distance threshold defaulting to `10.0` NQ points and an inclusive comparison (`<= threshold`).
- **D-09:** Emit machine-learning-friendly proximity features in addition to boolean flags: signed distance to each level, nearest-level label, nearest-level distance, and a count of how many structural levels fall within threshold on that row.

### Validation and downstream compatibility
- **D-10:** Restrict the baseline validation target to prior-day RTH value area levels that can be checked against a reference volume-profile chart; overnight value area validation is explicitly deferred to Phase 7.
- **D-11:** Preserve strict causality: a row on trading date `T` may only see structural levels computed from completed sessions before that row's RTH activity, never same-session developing profile information.
- **D-12:** Shape artifacts and column names for direct use by later setup-detection and analytics phases, favoring explicit numeric features over presentation-only summaries so the same outputs can feed both rule-based signals and later ML feature engineering.

### Claude's Discretion
- Exact helper/module boundaries for profile construction, artifact writing, and proximity enrichment.
- The precise fair-value-center metric used for `POC` tie-breaking, as long as it is deterministic and documented.
- Additional quality/reporting columns that make missing prior-session inputs easier to audit.

### Deferred Ideas (OUT OF SCOPE)
- Overnight value area (`STRC-02`) and other Globex-derived structural references belong to Phase 7, not this baseline phase.
- LVNs, HTF balance extremes, and richer composite profile analytics belong to the later volume-profile phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STRC-01 | System computes prior-day value area - VAH, VAL, and POC - from trade volume distribution | Session-level artifact from prior completed RTH trade rows only; native price-level histogram; deterministic POC and 70% expansion rules |
| STRC-07 | System detects when price is within configurable proximity of a structural level (default +/-10 NQ points) | Row-aligned enrichment with carried prior-day levels, configurable threshold, signed distances, nearest-level metadata, and inclusive boolean flags |
</phase_requirements>

## Summary

Phase 03 should extend the existing Phase 2 pattern instead of inventing a separate subsystem: load the canonical Phase 1 cache, isolate completed RTH trade rows, compute one prior-session structural record per `trading_date`, then join those prior-session levels back onto the full row stream as reusable numeric features. The codebase already uses Polars window expressions, row-stable joins, parquet artifacts, and CLI subcommands per phase; Phase 03 fits directly into that shape.

The main planning risk is not the profile math itself, but reproducibility. The planner needs to lock down deterministic tie-breaking, explicit handling for missing prior sessions, and a row-aligned schema that later phases can consume without recomputing anything. The environment audit also matters: the repo declares `polars>=1.39.3,<1.40` and `pytest>=9.0.2,<10`, but the current machine has `polars 1.39.2` and `pytest 8.4.2`, so validation commands should use `python -m pytest` and the plan should include an environment-sync decision if exact dependency parity matters.

**Primary recommendation:** Implement Phase 03 as a new `src/vwap_revert/indicators/structural_levels.py` module plus a `build-phase3-structural-levels` CLI command that emits both a session-level parquet artifact and a row-aligned enriched parquet artifact, following the Phase 2 writer/validation pattern.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `polars` | Repo target `>=1.39.3,<1.40`; current env `1.39.2`; latest PyPI release `1.39.3` (2026-03-20) | Session filtering, grouped volume profile aggregation, deterministic joins, row-aligned enrichment | Already used across Phases 1-2 and supports the exact `group_by`, `over`, forward-fill, and parquet patterns this phase needs |
| `pyarrow` | Repo target `>=23.0.1,<24`; current env `23.0.1`; PyPI `23.0.1` (2026-02-16) | Partitioned parquet IO for reusable artifacts | Phase 1 already depends on Arrow-backed parquet writing and Phase 03 should stay artifact-compatible |
| `numpy` | Repo target `>=2.4.4,<3`; current env `2.4.4` | Small scalar math helpers for tie-break metrics if needed | Existing stack already includes NumPy; use only for scalar helpers, not dataframe orchestration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | Repo target `>=9.0.2,<10`; current env `8.4.2` | Unit and CLI artifact tests | Use for deterministic fixtures covering POC/VA expansion, missing-session behavior, and row-aligned proximity outputs |
| `ruff` | Repo target `>=0.13,<0.14`; installed package `0.15.6`; CLI not on PATH | Linting/formatting | Use only after deciding whether to align the environment with the repo pin |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native-price profile in Polars | Bucketed histogram in NumPy/Pandas | Simpler loops, but loses price-resolution and breaks the locked Phase 03 decision |
| Row-aligned enriched parquet | Session-only report plus ad hoc downstream joins | Lower storage, but pushes causality and schema complexity into later phases |
| New top-level package | Reuse `src/vwap_revert/indicators` | A separate package boundary adds ceremony without reducing complexity |

**Installation:**
```bash
python -m pip install -e .[dev]
```

**Version verification:**
- `polars` latest release `1.39.3` on PyPI, published 2026-03-20.
- `pyarrow` latest release `23.0.1` on PyPI, published 2026-02-16.
- Local environment currently imports `polars 1.39.2`, `pyarrow 23.0.1`, `numpy 2.4.4`, `pytest 8.4.2`, and `ruff 0.15.6`.

## Architecture Patterns

### Recommended Project Structure
```text
src/
|-- vwap_revert/
|   |-- cli.py                         # Phase command registration
|   |-- indicators/
|   |   |-- vwap.py                    # Existing Phase 2 pattern
|   |   `-- structural_levels.py       # Phase 3 profile + enrichment logic
|   `-- data_pipeline/
|       `-- cache.py                   # Canonical cache reload surface
tests/
`-- indicators/
    |-- test_vwap.py                   # Existing indicator test shape
    |-- test_vwap_validation.py        # Existing artifact/CLI test shape
    `-- test_structural_levels.py      # New profile/proximity tests
```

### Pattern 1: Build a session-level prior-day structural artifact first
**What:** Aggregate RTH trade rows by `trading_date` and `price`, compute per-session `POC`, `VAH`, `VAL`, quality metadata, then shift those results forward one `trading_date` so each current session references the prior completed session only.
**When to use:** Always. This is the causal source of truth for every later row-level feature.
**Example:**
```python
trade_rows = (
    df.filter(pl.col("is_rth") & pl.col("side").is_in(["A", "B"]))
    .sort(["trading_date", "ts_recv"])
)

profile = (
    trade_rows.group_by(["trading_date", "price"])
    .agg(pl.col("size").sum().alias("traded_volume"))
    .sort(["trading_date", "price"])
)
```
Source: local Phase 2 pattern and Polars `group_by`/window expression docs

### Pattern 2: Keep deterministic tie-breaks in explicit helper functions
**What:** Resolve `POC` ties and 70% expansion ties in pure, well-tested helpers operating on one session profile at a time.
**When to use:** For any logic that cannot be expressed transparently as a single Polars expression without obscuring the deterministic rules.
**Example:**
```python
def choose_poc(price_levels: list[dict[str, float]], fair_value_center: float) -> float:
    peak_volume = max(row["traded_volume"] for row in price_levels)
    candidates = [row["price"] for row in price_levels if row["traded_volume"] == peak_volume]
    return min(candidates, key=lambda price: (abs(price - fair_value_center), price))
```
Source: Phase 03 locked decisions D-05 and D-06

### Pattern 3: Join structural levels back onto the full row stream
**What:** Follow Phase 2's `with_row_index` + left join pattern so every current-session row receives the active prior-day `VAH`, `VAL`, and `POC`, along with distance and boolean columns.
**When to use:** For the reusable downstream artifact consumed by Phase 4 and later analysis.
**Example:**
```python
base = df.with_row_index("__row")
enriched = (
    base.join(session_levels, on="trading_date", how="left")
    .sort("__row")
    .drop("__row")
)
```
Source: [src/vwap_revert/indicators/vwap.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/indicators/vwap.py)

### Anti-Patterns to Avoid
- **Same-session profile leakage:** Do not compute or expose developing current-session value area columns. Phase 03 is prior-session only.
- **Quote-row synthetic volume:** Do not count `side == "N"` rows toward the profile histogram.
- **Implicit fallback to older sessions:** If the immediately prior `trading_date` session is missing or unusable, emit null levels and explicit quality fields.
- **Opaque vectorized tie-breaking:** If a dense Polars expression makes the deterministic rule hard to reason about, keep that step in a small helper and test it directly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session boundary logic | New date/session parser | Existing `label_sessions()` outputs from Phase 1 | DST and trading-date logic are already locked and tested |
| Cache reload | Custom file scanner | `scan_canonical_cache()` | Keeps Phase 03 on the canonical dataset boundary |
| Row-aligned artifact joins | Manual Python loops over rows | Polars joins plus stable row index pattern from Phase 2 | Faster, simpler, and already proven in the repo |
| Validation artifact layout | One-off CSV script outside the package | Same writer pattern as `write_vwap_validation_export()` | Keeps manual audit artifacts consistent across phases |

**Key insight:** The hard part in this domain is causal session semantics and deterministic outputs, not dataframe plumbing. Reuse the existing cache/session/CLI/writer surfaces and spend planning effort on profile correctness and test coverage.

## Common Pitfalls

### Pitfall 1: Counting quote-only rows in the profile
**What goes wrong:** VAH/VAL/POC reflect quote persistence rather than traded volume.
**Why it happens:** The canonical BBO frame includes both trade-bearing and quote-only seconds.
**How to avoid:** Filter to `side in {"A", "B"}` before any profile aggregation.
**Warning signs:** Profile rows exist for prices that never traded during RTH.

### Pitfall 2: Leaking same-session information
**What goes wrong:** Current-session rows see their own developing structural levels.
**Why it happens:** Joining same-day session aggregates back onto the same `trading_date` without shifting.
**How to avoid:** Compute session levels per day, then map them to the next session as prior-day references.
**Warning signs:** Rows for the first session in a fixture have non-null levels without a prior day present.

### Pitfall 3: Non-deterministic tie resolution
**What goes wrong:** Rebuilds produce different `POC`, `VAH`, or `VAL` when multiple prices have equal volume.
**Why it happens:** The algorithm relies on dataframe sort side effects or unstable iteration order.
**How to avoid:** Encode the tie-break rule explicitly and unit test it with exact expected levels.
**Warning signs:** The same fixture yields different outputs after refactoring or dependency updates.

### Pitfall 4: Treating missing prior sessions as recoverable by substitution
**What goes wrong:** Structural references silently skip a missing day and use an older session.
**Why it happens:** A planner optimizes for non-null outputs instead of strict causality.
**How to avoid:** Emit null levels and quality metadata when the immediately prior `trading_date` is absent or unusable.
**Warning signs:** The first valid session after a data gap still carries populated levels.

### Pitfall 5: Environment mismatch hiding test failures
**What goes wrong:** Planning assumes repo-pinned versions are installed, but the machine runs different ones.
**Why it happens:** `pyproject.toml` and the current Python environment diverge.
**How to avoid:** Use `python -m pytest` in plan commands and decide up front whether to normalize the environment.
**Warning signs:** `pytest` is not on PATH, or lint/test behavior differs from declared dependency pins.

## Code Examples

Verified patterns from local code and official docs:

### Row-stable join-back pattern
```python
base = df.with_row_index("__row")
enriched = base.join(indicator_rows, on=["trading_date", "ts_recv"], how="left").sort("__row").drop("__row")
```
Source: [src/vwap_revert/indicators/vwap.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/indicators/vwap.py)

### Per-group cumulative/window calculation
```python
df.with_columns(
    pl.col("size").cum_sum().over("trading_date").alias("cum_volume")
)
```
Source: https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.over.html

### Partitioned parquet artifact writing
```python
df.write_parquet(
    output_dir,
    use_pyarrow=True,
    compression="zstd",
    pyarrow_options={"partition_cols": ["trading_date"]},
)
```
Source: [src/vwap_revert/data_pipeline/cache.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/data_pipeline/cache.py)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full-session or 24h profiles for all structural references | RTH-only prior-session profile for the baseline phase | Locked in Phase 03 context on 2026-04-02 | Keeps structural references aligned with the strategy's RTH execution model |
| Bucketed profile bins chosen up front | Native traded price levels with no irreversible aggregation | Locked in Phase 03 context on 2026-04-02 | Preserves maximum detail for later ML feature work |
| Session summaries only | Session artifact plus row-aligned enriched artifact | Established by Phase 2 and reinforced in Phase 03 decisions | Makes later setup detection a simple column filter instead of a join-heavy recomputation |

**Deprecated/outdated:**
- Using quote-derived or midpoint-derived synthetic volume in the profile: conflicts with Phase 03 D-02 and would bias value area math.
- Treating prior-day structural levels as presentation-only chart annotations: later phases need explicit numeric columns.

## Open Questions

1. **What exact fair-value-center metric should the `POC` tie-break use?**
   - What we know: It must be deterministic and documented.
   - What's unclear: Whether to use session VWAP, midpoint of candidate price range, or another center metric.
   - Recommendation: Use session RTH VWAP from the same prior-day trade rows because it is already meaningful in this project and easy to explain.

2. **Should the row-aligned Phase 03 artifact be built from Phase 1 directly or from the Phase 2 enriched parquet?**
   - What we know: Phase 03 only depends on Phase 1 in the roadmap, but later phases will need both VWAP and structural columns together.
   - What's unclear: Whether the planner wants Phase 03 to stay dependency-pure or optimize for downstream convenience.
   - Recommendation: Keep the structural computation rooted in Phase 1 data, but allow the CLI to optionally enrich an input frame that already includes Phase 2 columns.

3. **How much quality metadata should the session artifact carry?**
   - What we know: Missing/unusable prior sessions must be explicit.
   - What's unclear: Minimum viable fields for planner acceptance.
   - Recommendation: Include at least `source_trading_date`, `levels_available`, `quality_status`, `profile_trade_rows`, and `profile_total_volume`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Package runtime and CLI | Yes | 3.14.3 | - |
| `polars` | Phase 03 dataframe engine | Yes | 1.39.2 | Sync to repo target `>=1.39.3,<1.40` if version parity is required |
| `pyarrow` | Parquet artifact writing | Yes | 23.0.1 | - |
| `numpy` | Scalar helper math | Yes | 2.4.4 | Pure Python helper logic if necessary |
| `python -m pytest` | Automated validation | Yes | 8.4.2 | - |
| `pytest` on PATH | Direct CLI invocation | No | - | Use `python -m pytest` |
| `ruff` package | Linting/formatting | Yes | 0.15.6 | - |
| `ruff` on PATH | Direct CLI invocation | No | - | Use `python -m ruff` after confirming compatibility |

**Missing dependencies with no fallback:**
- None identified for Phase 03 planning.

**Missing dependencies with fallback:**
- `pytest` CLI is not on PATH; use `python -m pytest`.
- `ruff` CLI is not on PATH; use `python -m ruff` if linting is part of the plan.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 8.4.2` installed, repo declares `pytest>=9.0.2,<10` |
| Config file | `pyproject.toml` |
| Quick run command | `python -m pytest tests/indicators/test_structural_levels.py -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STRC-01 | Prior-day `VAH`/`VAL`/`POC` computed from prior completed RTH trade distribution only | unit | `python -m pytest tests/indicators/test_structural_levels.py -q` | No - Wave 0 |
| STRC-07 | Proximity flags/distances use configurable inclusive threshold against carried prior-day levels | unit | `python -m pytest tests/indicators/test_structural_levels.py -q` | No - Wave 0 |
| STRC-01, STRC-07 | CLI writes session artifact, enriched artifact, and validation export | integration | `python -m pytest tests/indicators/test_structural_levels_validation.py -q` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/indicators/test_structural_levels.py -q`
- **Per wave merge:** `python -m pytest tests/indicators -q`
- **Phase gate:** `python -m pytest -q`

### Wave 0 Gaps
- [ ] `tests/indicators/test_structural_levels.py` - deterministic unit coverage for POC ties, value-area expansion, missing prior session, and proximity features
- [ ] `tests/indicators/test_structural_levels_validation.py` - artifact writer and CLI coverage mirroring Phase 2
- [ ] Pytest cache warning mitigation - current workspace hits a `.pytest_cache` access warning; either ignore it, disable cacheprovider, or configure a writable cache dir in commands if needed

## Sources

### Primary (HIGH confidence)
- [Local repo context] `.planning/phases/03-simple-structural-levels/03-CONTEXT.md` - locked Phase 03 decisions and scope
- [Local repo code] [src/vwap_revert/cli.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/cli.py) - established phase CLI pattern
- [Local repo code] [src/vwap_revert/indicators/vwap.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/indicators/vwap.py) - row-aligned artifact and validation writer pattern
- [Local repo tests] [tests/indicators/test_vwap.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/tests/indicators/test_vwap.py) and [tests/indicators/test_vwap_validation.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/tests/indicators/test_vwap_validation.py) - existing validation shape
- https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.over.html - verified window-expression behavior used by existing patterns
- https://pypi.org/project/polars/0.14.29/ - release history showing `1.39.3` published 2026-03-20
- https://pypi.org/project/pyarrow/ - release history showing `23.0.1` published 2026-02-16

### Secondary (MEDIUM confidence)
- https://pypi.org/project/numpy - package metadata used only to confirm NumPy remains a standard supporting dependency
- Local environment inspection via `python -m pip show` and `python -m pytest --version` - confirms runnable versions in this workspace

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - the stack is already present in the repo and mostly verified against current package metadata
- Architecture: HIGH - Phase 2 provides a direct implementation template for Phase 3
- Pitfalls: HIGH - the major failure modes are explicit in the locked decisions and visible from current code patterns

**Research date:** 2026-04-02
**Valid until:** 2026-05-02
