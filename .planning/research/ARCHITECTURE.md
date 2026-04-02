# Architecture Research

**Domain:** NQ Futures VWAP Reversion Backtesting
**Researched:** 2026-04-01
**Confidence:** HIGH

## Standard Architecture

### System Overview

This is a **vectorized pipeline** backtest, not an event-driven engine. The strategy rules are fully mechanical, the data is BBO (no order book depth), and the goal is research iteration speed — not production-grade execution simulation. Event-driven architecture adds complexity that buys nothing here.

The system is a six-stage data pipeline where each stage transforms a DataFrame and passes it downstream:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        STAGE 1: INGEST                              │
│  CSV files → filter columns → dtype optimize → front-month filter   │
│  Output: continuous front-month 1s timeseries (~50-70M rows)        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE 2: SESSION STRUCTURE                      │
│  UTC→ET conversion → session boundaries → RTH/Globex/ON labels     │
│  Output: timeseries with session_id, session_type, trading_date     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE 3: INDICATORS                             │
│  ┌──────────────┐  ┌────────────────┐  ┌───────────────────┐       │
│  │ VWAP Engine   │  │ Volume Profile │  │ Regime Classifier │       │
│  │ D/W/M + σ     │  │ Daily + HTF    │  │ Realized Vol      │       │
│  │ bands         │  │ POC/VAH/VAL/   │  │ → short/long γ    │       │
│  │               │  │ LVN detection  │  │                   │       │
│  └──────┬───────┘  └───────┬────────┘  └─────────┬─────────┘       │
│         └──────────────────┼──────────────────────┘                 │
│                            ▼                                        │
│              Merged indicator columns                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE 4: SETUP DETECTION                        │
│  Time filter (RTH first 1-2h) → deviation check (1.7-3σ) →        │
│  structural level check → continuation failure detection            │
│  Output: DataFrame of candidate trade setups with context           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE 5: TRADE SIMULATION                       │
│  Walk setups chronologically → entry after failure confirmation →   │
│  target VWAP/POC reversion → stop logic → position tracking         │
│  Output: trade log with entry/exit/P&L/context                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE 6: ANALYTICS                              │
│  Win rate, profit factor, Sharpe, drawdown → regime breakdown →    │
│  σ-band breakdown → CSV/JSON export                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Vectorized, Not Event-Driven

| Concern | Event-Driven | Vectorized Pipeline | This Project |
|---------|-------------|-------------------|--------------|
| Speed | Slow (row-by-row) | Fast (array ops) | Need fast iteration over 100M+ rows |
| Lookahead bias | Eliminated by design | Must be careful with indexing | Manageable — signals use only past data by construction |
| Execution realism | High (models fills, slippage) | Low (assumes fill at price) | BBO data can't model fills anyway |
| Complexity | High (event queue, handlers) | Low (DataFrame transforms) | Single developer, research tool |
| Live transition | Easy | Hard | Out of scope per PROJECT.md |

The one exception is **Stage 5 (Trade Simulation)**, which must walk forward chronologically to track position state. This is a small sequential loop over the setup DataFrame (hundreds to low thousands of rows), not the full 50M+ row timeseries.

### Component Responsibilities

| Component | Module | Input | Output | Stateful? |
|-----------|--------|-------|--------|-----------|
| Data Loader | `data/loader.py` | CSV file paths | Raw DataFrame with optimized dtypes | No |
| Contract Resolver | `data/contracts.py` | Raw DataFrame with all symbols | Filtered front-month DataFrame | No |
| Session Builder | `data/sessions.py` | Front-month DataFrame (UTC) | DataFrame with ET times, session labels | No |
| VWAP Engine | `indicators/vwap.py` | Session-structured DataFrame | DataFrame + D/W/M VWAP and σ-band columns | No |
| Volume Profile Builder | `indicators/volume_profile.py` | Session-structured DataFrame | Per-session profile objects + HTF profile; LVN/POC/VAH/VAL levels joined to timeseries | Yes (rolling 180-day window) |
| Regime Classifier | `indicators/regime.py` | Session-structured DataFrame | Session-level regime labels joined to timeseries | No |
| Setup Scanner | `strategy/scanner.py` | Fully-enriched DataFrame | Setup DataFrame (subset of rows meeting all conditions) | No |
| Failure Detector | `strategy/failure.py` | Setup candidates + surrounding price action | Confirmed setups with failure bar timestamp | No |
| Trade Simulator | `strategy/simulator.py` | Confirmed setups + full timeseries | Trade log DataFrame | Yes (position state) |
| Analytics | `analytics/performance.py` | Trade log DataFrame | Metrics dict + breakdown DataFrames | No |
| Output Writer | `analytics/output.py` | Metrics + breakdowns | CSV/JSON files | No |
| Config | `config.py` | YAML/dict | Parameter namespace | No |
| Pipeline Orchestrator | `pipeline.py` | Config | Final analytics output | No |

## Recommended Project Structure

```
vwap_revert/
├── config.py                  # Strategy parameters, file paths, thresholds
├── pipeline.py                # Orchestrates all stages end-to-end
├── run.py                     # CLI entry point
│
├── data/
│   ├── __init__.py
│   ├── loader.py              # CSV reading with dtype optimization and column selection
│   ├── contracts.py           # Front-month detection, quarterly roll logic
│   └── sessions.py            # UTC→ET, session boundary detection, RTH/Globex labeling
│
├── indicators/
│   ├── __init__.py
│   ├── vwap.py                # Daily/Weekly/Monthly VWAP + σ bands
│   ├── volume_profile.py      # Daily + HTF rolling profiles, POC/VAH/VAL/LVN
│   └── regime.py              # Realized volatility → gamma regime classification
│
├── strategy/
│   ├── __init__.py
│   ├── scanner.py             # Setup condition detection (time + σ + structure)
│   ├── failure.py             # Continuation failure mechanical definition
│   └── simulator.py           # Trade entry/exit/position tracking
│
├── analytics/
│   ├── __init__.py
│   ├── performance.py         # Win rate, PF, Sharpe, drawdown, regime/σ breakdowns
│   └── output.py              # CSV/JSON export formatting
│
├── tests/
│   ├── test_contracts.py      # Roll date detection tests
│   ├── test_vwap.py           # VWAP calculation correctness
│   ├── test_volume_profile.py # Profile construction, LVN detection
│   └── test_simulator.py      # Trade simulation edge cases
│
└── output/                    # Generated results (gitignored)
    ├── trades.csv
    ├── summary.json
    └── breakdowns/
```

**Why this structure:**
- `data/` handles everything about getting raw data into a clean timeseries — the "E" in ETL
- `indicators/` computes derived values that the strategy consumes — pure functions on DataFrames
- `strategy/` contains all trading logic — this is the only place trade decisions live
- `analytics/` is post-trade — never touches strategy logic
- `pipeline.py` wires stages together — the only file that imports from all packages
- `config.py` is a single source of truth for all tunable parameters (σ thresholds, time windows, roll dates, etc.)

## Architectural Patterns

### Pattern 1: DataFrame-In, DataFrame-Out Stages

Every stage (except analytics output) takes a DataFrame and returns a DataFrame with additional columns. This makes stages composable, independently testable, and easy to inspect at any point.

```python
def compute_daily_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Add daily_vwap, daily_vwap_std, daily_vwap_upper_1s ... columns."""
    trades = df[df["side"].isin(["B", "A"])].copy()
    grouped = trades.groupby("trading_date")

    cumulative_pv = grouped.apply(lambda g: (g["price"] * g["size"]).cumsum())
    cumulative_vol = grouped["size"].cumsum()

    df["daily_vwap"] = cumulative_pv / cumulative_vol
    df["daily_vwap"].ffill(inplace=True)
    # ... σ bands computed from rolling deviation
    return df
```

### Pattern 2: Centralized Configuration

All tunable parameters live in one place. Strategy logic reads from config, never contains magic numbers.

```python
@dataclass
class Config:
    # Data paths
    data_dir: Path
    output_dir: Path

    # Contract
    instrument: str = "NQ"
    roll_day_offset: int = -1  # Thursday before expiry Friday

    # VWAP
    sigma_entry_min: float = 1.7
    sigma_entry_max: float = 3.0
    sigma_bands: list[float] = field(default_factory=lambda: [1.0, 1.5, 2.0, 2.5, 3.0, 4.0])

    # Volume Profile
    htf_lookback_days: int = 180
    profile_tick_size: float = 0.25
    value_area_pct: float = 0.70

    # Session
    rth_start: time = time(9, 30)
    rth_end: time = time(16, 0)
    scan_window_hours: float = 2.0

    # Trade
    tick_value: float = 5.00
    point_value: float = 20.00

    # Failure detection
    failure_lookback_bars: int = 5
    failure_reversal_ticks: int = 4
```

### Pattern 3: Explicit Session Boundaries

Time-based logic is the #1 source of bugs in futures backtesting. Make sessions first-class objects rather than computing boundaries repeatedly.

```python
SESSIONS = {
    "globex": (time(18, 0), time(9, 30)),   # Prior day 6PM ET → 9:30AM ET
    "rth":    (time(9, 30), time(16, 0)),    # 9:30AM → 4:00PM ET
    "scan":   (time(9, 30), time(11, 30)),   # Trading window subset
}
```

Each row in the DataFrame gets a `session_type` and `trading_date` column assigned once during Stage 2. All downstream logic filters on these columns — never re-derives session boundaries.

### Pattern 4: Volume Profile as a Lookup Structure

Volume profiles are not per-row values — they're per-session (or per-window) distributions. Store them as a separate structure keyed by date, and join derived levels (POC, VAH, VAL, LVNs) back to the main DataFrame.

```python
@dataclass
class VolumeProfile:
    trading_date: date
    price_bins: np.ndarray       # Price levels
    volume_bins: np.ndarray      # Volume at each level
    poc: float                   # Point of control
    vah: float                   # Value area high
    val: float                   # Value area low
    lvns: list[float]            # Low volume nodes

class ProfileStore:
    """Indexed collection of daily profiles with HTF rolling window."""
    profiles: dict[date, VolumeProfile]

    def get_htf_profile(self, as_of: date, lookback: int = 180) -> VolumeProfile:
        """Merge daily profiles within window into composite."""
        ...
```

## Data Flow

### Processing Pipeline (Detailed)

```
884 CSV files on disk
        │
        ▼
[1] LOAD (chunked read, dtype-optimized)
    - Read only needed columns: ts_event, side, price, size,
      bid_px_00, ask_px_00, bid_sz_00, ask_sz_00, symbol
    - Apply dtypes upfront: float32 for prices, int32 for sizes,
      category for symbol/side
    - Concatenate into single DataFrame
    - Memory: ~1.5-2.5 GB after optimization
        │
        ▼
[2] FILTER TO FRONT MONTH
    - Parse symbol column → extract contract month code + year
    - For each calendar date, identify the front-month contract:
      active contract until roll day (Thursday before 3rd Friday
      of expiration month), then switch to next quarter
    - Drop spread symbols, back-month contracts
    - Row count drops ~60-70% (most rows are non-front-month)
    - Memory: ~0.5-1.0 GB
        │
        ▼
[3] BUILD SESSION STRUCTURE
    - Convert ts_event (UTC nanoseconds) → US/Eastern datetime
    - Assign trading_date (date the RTH session belongs to;
      overnight Globex maps to next trading date)
    - Label session_type: 'globex_overnight', 'rth', 'rth_scan_window'
    - Compute mid_price = (bid_px_00 + ask_px_00) / 2 for BBO-only rows
    - Sort by timestamp (should already be sorted, but verify)
        │
        ▼
[4a] COMPUTE VWAP + BANDS ──────────────────────────────────┐
    - Daily: reset cumulative P×V and V at each RTH open      │
    - Weekly: reset at Monday's Globex open                    │
    - Monthly: reset at 1st of month                          │
    - σ bands: rolling std of (price - VWAP), scaled           │
    - Forward-fill VWAP during no-trade intervals              │
    - Output: 6 new columns per timeframe (vwap + bands)       │
                                                               │
[4b] BUILD VOLUME PROFILES ────────────────────────────────────┤
    - Daily: bin trade prices at tick_size resolution,          │
      accumulate volume per bin within each session             │
    - Compute POC, VAH, VAL from 70% value area               │
    - Detect LVNs: bins with volume < threshold relative       │
      to surrounding bins                                      │
    - HTF: maintain rolling 180-day composite profile           │
      (sum daily profiles within window)                       │
    - Join POC/VAH/VAL/LVN levels to timeseries as             │
      "structural level" reference columns                     │
                                                               │
[4c] CLASSIFY REGIME ──────────────────────────────────────────┘
    - Compute realized volatility per session (std of returns
      over trailing N sessions)
    - Classify: short_gamma (high vol) vs long_gamma (low vol)
    - Threshold: configurable percentile split or absolute level
    - Join regime label to timeseries per-session
        │
        ▼ (all indicator columns now on single DataFrame)
[5] SCAN FOR SETUPS
    - Filter: session_type == 'rth_scan_window'
    - Filter: sigma_deviation BETWEEN sigma_entry_min AND sigma_entry_max
    - Filter: price near structural level (within N ticks of
      any HTF POC/VAH/VAL/LVN or prior session VA edge)
    - For each candidate, extract surrounding bars and run
      failure detection logic
    - Output: setup DataFrame with columns:
      [timestamp, direction, sigma_at_entry, structural_level_type,
       regime, failure_bar_ts, ...]
        │
        ▼
[6] SIMULATE TRADES
    - Sequential walk through setups (chronological order)
    - Entry: at failure_bar close or next bar open
    - Target: daily_vwap, weekly_vwap, or developing_poc
      (configurable hierarchy)
    - Stop: configurable (e.g., N ticks beyond entry extreme,
      or time-based exit at session end)
    - Track: position state, partial fills if desired
    - Output: trade log DataFrame with:
      [trade_id, entry_time, exit_time, direction, entry_price,
       exit_price, pnl_ticks, pnl_dollars, duration_seconds,
       sigma_at_entry, regime, structural_level_type, exit_reason]
        │
        ▼
[7] COMPUTE ANALYTICS
    - Aggregate: win_rate, avg_win, avg_loss, profit_factor,
      max_drawdown, sharpe_ratio, total_pnl
    - Breakdown by regime: short_gamma vs long_gamma
    - Breakdown by σ band: 1.7-2.2σ, 2.2-3σ, 3σ+
    - Breakdown by structural level type
    - Breakdown by day of week, month
    - Export: trades.csv, summary.json, breakdowns/*.csv
```

### State Management

Most stages are stateless DataFrame transforms. Two components carry state:

| Component | State | Scope | Reset |
|-----------|-------|-------|-------|
| Volume Profile Store | Rolling 180-day composite profile | Cross-session | Sliding window — oldest session drops off |
| Trade Simulator | Current position, cumulative P&L, drawdown tracker | Entire backtest | Never (tracks full equity curve) |

Both are small in memory. The profile store holds at most 180 daily profiles (~180 × ~1000 price bins × 8 bytes ≈ 1.4 MB). The trade simulator tracks a single-contract position.

## Performance Architecture

### Memory Budget

| Stage | Estimated Memory | Notes |
|-------|-----------------|-------|
| Raw load (all files) | 2.5 GB | Before filtering, with dtype optimization |
| After front-month filter | 0.8-1.2 GB | ~30-40% of rows survive |
| With indicators | 1.5-2.0 GB | Additional columns add ~50% |
| Setup DataFrame | < 10 MB | Hundreds to thousands of rows |
| Trade log | < 1 MB | Hundreds of trades |
| **Peak** | **~2.5 GB** | During initial load before filtering |

This fits comfortably in 8 GB RAM. No need for out-of-core processing or chunked computation for the core pipeline.

### Loading Strategy: Bulk Load with Early Filter

Rather than processing files one at a time, load all 884 files and concatenate — but apply aggressive early filtering:

```python
def load_all(data_dir: Path, usecols: list[str], dtypes: dict) -> pd.DataFrame:
    frames = []
    for csv_path in sorted(data_dir.glob("*.csv")):
        chunk = pd.read_csv(
            csv_path,
            usecols=usecols,
            dtype=dtypes,
            parse_dates=False,  # Parse timestamps manually (faster)
        )
        chunk = chunk[chunk["symbol"].str.startswith("NQ")]  # Drop non-NQ early
        chunk = chunk[~chunk["symbol"].str.contains("-")]     # Drop spreads early
        frames.append(chunk)
    return pd.concat(frames, ignore_index=True)
```

**Why not chunked-per-file processing:** The VWAP and volume profile calculations span multiple days (weekly VWAP, 180-day profile). Processing files independently would require complex state management across file boundaries. Since the data fits in memory after filtering, bulk load is simpler and eliminates boundary-crossing bugs.

### Dtype Optimization

| Column | Raw Type | Optimized Type | Savings |
|--------|----------|---------------|---------|
| `ts_event` | int64 (ns) | int64 | 0% (need full precision) |
| `price` | float64 | float32 | 50% (NQ prices have 0.25 resolution) |
| `size` | int64 | int32 | 50% (volume never exceeds 2B) |
| `bid_px_00` | float64 | float32 | 50% |
| `ask_px_00` | float64 | float32 | 50% |
| `bid_sz_00` | int64 | int32 | 50% |
| `ask_sz_00` | int64 | int32 | 50% |
| `side` | object | category | ~90% (3 unique values) |
| `symbol` | object | category | ~85% (< 20 unique values) |

Expected savings: ~50-60% reduction from naive `read_csv`.

### Computation Hotspots

| Operation | Rows | Strategy |
|-----------|------|----------|
| VWAP cumulative sum | ~30M trade rows | `groupby().cumsum()` — vectorized, fast |
| Volume profile binning | ~30M trade rows | `np.histogram` per session — vectorized |
| HTF profile rolling | 884 sessions × 180-day window | Sum pre-computed daily histograms (array addition, not re-binning) |
| σ band computation | ~50M all rows | `groupby().expanding().std()` — vectorized |
| Setup scanning | ~50M rows → filter to ~2M scan-window rows | Boolean mask chain — very fast |
| Failure detection | ~2K-10K candidate rows | Small loop or vectorized pattern match |
| Trade simulation | ~500-2K setups | Simple sequential loop — negligible |

**The bottleneck is Stage 1 (I/O) and Stage 4a (VWAP cumsum).** Both are already efficient with pandas vectorized operations. The HTF volume profile is potentially expensive but the "sum daily histograms" approach avoids re-processing raw data.

### Optional: Parquet Cache Layer

After the first run, save the filtered + session-structured DataFrame as a single Parquet file. Subsequent runs skip CSV parsing entirely:

```python
CACHE_PATH = output_dir / "cache" / "front_month_sessions.parquet"

if CACHE_PATH.exists() and not force_reload:
    df = pd.read_parquet(CACHE_PATH)
else:
    df = load_all(...)
    df = resolve_front_month(df, ...)
    df = build_sessions(df, ...)
    df.to_parquet(CACHE_PATH)
```

This reduces the reload time from ~3-5 minutes (CSV I/O) to ~5-10 seconds (Parquet I/O). Parquet also compresses the data ~5-10x on disk.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Event-Driven Overengineering

**What:** Building a full event queue with market data events, order events, fill events, and portfolio update events for a mechanical backtest on historical data.

**Why bad:** Adds 5-10x code complexity. No benefit when execution model is "fill at the price" (BBO data doesn't support realistic fill simulation). Slower by orders of magnitude.

**Instead:** Vectorized pipeline for indicator computation + small sequential loop for trade simulation only.

### Anti-Pattern 2: Per-File Independent Processing

**What:** Processing each CSV file as a self-contained unit, computing daily VWAP, scanning for setups, and simulating trades before moving to the next file.

**Why bad:** Weekly/monthly VWAP spans files. HTF volume profile spans 180 files. Contract roll logic needs cross-file context. Leads to complex state-passing between file iterations and subtle boundary bugs.

**Instead:** Bulk load → filter → single DataFrame. The data fits in memory.

### Anti-Pattern 3: Storing Indicators in Separate DataFrames

**What:** Keeping VWAP values in one DataFrame, volume profile levels in another, regime labels in a third, and joining them at scan time.

**Why bad:** Merge/join bugs, timestamp alignment issues, timezone mismatches between frames. Painful to debug when a setup's context doesn't match.

**Instead:** Add indicator columns directly to the main DataFrame. One truth, one index.

### Anti-Pattern 4: Timezone Conversion at Point-of-Use

**What:** Converting UTC to Eastern time wherever session logic is needed, rather than once upfront.

**Why bad:** DST boundary bugs (EST vs EDT), inconsistent conversion across components, off-by-one-hour errors near DST transitions that silently corrupt session boundaries.

**Instead:** Convert once in Stage 2, store as tz-aware datetime with `US/Eastern`. All downstream code works in Eastern time. The March and November DST transitions within the data range (2021-2023) will exercise both paths.

### Anti-Pattern 5: Magic Numbers in Strategy Logic

**What:** Hardcoding `1.7`, `3.0`, `180`, `0.70` etc. directly in computation functions.

**Why bad:** Can't sweep parameters. Can't audit what values produced which results. Different runs become irreproducible.

**Instead:** All parameters in `Config`. Pass config to every stage. Log the config alongside results.

### Anti-Pattern 6: Computing VWAP from BBO Mid-Price

**What:** Using `(bid + ask) / 2` as the price input for VWAP calculation.

**Why bad:** VWAP is a volume-weighted metric defined on actual trades. Mid-price has no volume. Mixing trade prices (when `side` is B or A) with mid-prices (when `side` is N) produces a VWAP that doesn't match any standard definition.

**Instead:** Compute VWAP exclusively from rows where `side` in ('B', 'A') — these are actual trades with price and size. Forward-fill the VWAP value to cover no-trade intervals. Only use mid-price for "current price" comparisons, never for VWAP input.

### Anti-Pattern 7: Lookahead in Volume Profile Levels

**What:** Using the "final" daily volume profile (POC/VAH/VAL computed at session close) when scanning for setups during the session.

**Why bad:** The complete profile isn't known until the session ends. Using it at 9:45 AM creates lookahead bias — you're comparing price to levels that include 10:00 AM through 4:00 PM data.

**Instead:** Use the **prior session's** completed profile and the **HTF rolling profile** (which only includes completed sessions) as structural references. The developing session's profile is not yet finalized and should not be used for structural level identification.

## Suggested Build Order

Build order is dictated by data dependencies. Each stage requires the previous stage's output.

| Phase | Component | Depends On | Rationale |
|-------|-----------|------------|-----------|
| 1 | Data Loader + Contract Resolver + Session Builder | Nothing | Foundation — everything else needs clean, session-structured front-month data. Build and validate this first so all downstream work uses real data. |
| 2 | VWAP Engine (daily first, then weekly/monthly) | Phase 1 | Core indicator. Daily VWAP is the simplest and most critical. Weekly/monthly are mechanical extensions. Can validate against known VWAP values. |
| 3 | Volume Profile Builder (daily first, then HTF) | Phase 1 | Second core indicator. Daily profiles are independent per-session. HTF rolling is an aggregation of daily profiles — build daily first, HTF second. |
| 4 | Regime Classifier | Phase 1 | Independent of VWAP/profile. Needs only price returns per session. Can be built in parallel with Phase 2-3 but sequenced here for simplicity. |
| 5 | Setup Scanner + Failure Detector | Phases 2, 3, 4 | Consumes all indicators. This is the strategy logic — the intellectual core. Cannot be built until indicators exist. |
| 6 | Trade Simulator | Phase 5 | Mechanical execution of setups. Needs setup DataFrame + full timeseries for exit logic. |
| 7 | Analytics + Output | Phase 6 | Post-processing. Needs trade log. Straightforward aggregation and formatting. |

**Critical path:** Phases 1 → 2 → 5 → 6 → 7. Volume profile (Phase 3) and regime (Phase 4) can be built in parallel with VWAP (Phase 2) but both must complete before Phase 5.

## Sources

- [Vectorized vs Event-Driven Backtesting: Key Differences](https://asmr.education/faq/python-market-trading/vectorized-event-driven-backtesting-differences) — Confidence: MEDIUM
- [The Python Backtesting Landscape (2026)](https://python.financial/) — Confidence: MEDIUM
- [Pandas vs Polars vs DuckDB: What Data Scientists Should Use in 2026](https://www.analyticsinsight.net/amp/story/programming/pandas-vs-polars-vs-duckdb-what-data-scientists-should-use-in-2026) — Confidence: MEDIUM
- [How to Handle Large Data Processing with Pandas](https://oneuptime.com/blog/post/2026-02-02-python-pandas-large-data/view) — Confidence: MEDIUM
- [CME Quarterly Roll Timing](https://www.cmegroup.com/education/articles-and-reports/get-to-know-the-quarterly-roll-in-cme-fx-futures.html) — Confidence: HIGH (official CME source)
- PROJECT.md data format and constraints — Confidence: HIGH (project-specific)
