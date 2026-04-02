# Stack Research

**Domain:** NQ Futures VWAP Reversion Backtesting
**Researched:** 2026-04-01
**Confidence:** HIGH

## Decision: Custom Build, Not a Framework

No existing backtesting framework (Backtrader, VectorBT, NautilusTrader, Zipline) fits this project. The strategy requires custom computations — rolling multi-timeframe VWAP with sigma bands, HTF volume profile overlays, structural level confluence detection, gamma regime classification from realized vol, and mechanical continuation-failure identification from price action. Mapping all of this into a framework's abstractions would take longer than building from scratch, and the result would be harder to debug.

This is a single-strategy, single-instrument, backtest-only research tool. The framework overhead (portfolio management, multi-asset routing, order types, live trading hooks) is pure dead weight.

**Build it from composable libraries.** Polars for data I/O, NumPy+Numba for computation, pure Python for the event loop.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | 3.13.x | Runtime | Stable, well-supported by all numeric libraries. 3.14 is production-ready but Numba lags new Python versions. 3.13 is the safe sweet spot. | HIGH |
| Polars | ≥1.39.1 | Data loading, filtering, aggregation | 5-30x faster than Pandas for CSV reads, groupby, and filtering. Lazy evaluation via `scan_csv()` lets you filter front-month contracts *before* loading data into memory — critical when processing 884 files. Rust backend, automatic parallelization, no GIL. | HIGH |
| NumPy | ≥2.4.4 | Numeric computation (VWAP, bands, profiles) | `np.cumsum()` for VWAP is 5x faster than Pandas equivalent. All rolling/cumulative math lives here. NumPy arrays are the lingua franca between Polars output and Numba-accelerated functions. | HIGH |
| Numba | ≥0.65.0 | JIT compilation for hot loops | 2-10x speedup on the event-driven backtest loop and any per-bar computation that can't be vectorized (continuation-failure detection, trade state machine). `@njit` with `cache=True` for zero-warmup on subsequent runs. | HIGH |
| PyArrow | ≥23.0.1 | Parquet I/O, Arrow memory format | Polars' native interchange format. Used for the CSV→Parquet one-time conversion that turns 15GB of CSVs into ~3-5GB of Parquet files with 10x faster subsequent reads. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| `zoneinfo` | stdlib | UTC → US/Eastern timezone conversion | All session logic: RTH open detection (9:30 ET), overnight session splitting. Built into Python 3.9+, replaces pytz. | HIGH |
| `tzdata` | ≥2025.2 | IANA timezone database for Windows | Windows doesn't ship system TZ data — this package provides it. Required for `zoneinfo` to work on the user's Windows machine. | HIGH |
| `pytest` | ≥9.0.2 | Testing | Validate VWAP calculations against known values, verify front-month contract selection logic, test session boundaries around DST transitions. | HIGH |
| `dataclasses` | stdlib | Trade, Position, Signal data structures | Clean immutable records for the backtest event loop. No need for Pydantic or attrs in a CLI backtest tool. | HIGH |
| `pathlib` | stdlib | File path handling | Cross-platform path resolution for the 884 CSV files. | HIGH |
| `logging` | stdlib | Runtime diagnostics | Track which files are processed, flag data anomalies (missing trades, gap days), report backtest progress. | HIGH |
| `json` | stdlib | Config and results output | Strategy parameters, backtest results. No need for YAML/TOML parsers. | HIGH |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest` | Unit + integration tests | Test VWAP math against hand-calculated values; test contract roll logic against known roll dates |
| `ruff` | Linting + formatting | Single tool replaces flake8, black, isort. Fast (Rust-based). Use `ruff check` and `ruff format`. |
| `mypy` | Optional type checking | Useful if type annotations are added, but not blocking for a research tool |
| Python REPL / Jupyter | Ad-hoc data exploration | Inspect individual day files, validate volume profiles visually |

## Installation

```bash
pip install polars>=1.39.1 numpy>=2.4.4 numba>=0.65.0 pyarrow>=23.0.1 tzdata>=2025.2 pytest>=9.0.2
```

Dev tools (optional):
```bash
pip install ruff mypy
```

No virtual environment manager is prescribed — user's choice (venv, conda, uv). The dependencies are minimal and conflict-free.

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|------------------------|
| Data engine | Polars | Pandas 3.0 | If you need tight scikit-learn/statsmodels integration (not needed here). Pandas 3.0 with PyArrow backend is better than 2.x but still 5-10x slower than Polars at this data scale. |
| Data engine | Polars | DuckDB | If you want SQL-based analytics or need to query data larger than RAM. Overkill here — filtered front-month NQ data fits comfortably in memory. |
| JIT compiler | Numba | Cython | If you need C-extension compilation. Numba is simpler (decorators, not separate build step) and fast enough for this use case. |
| Backtest framework | Custom | VectorBT | If you're doing parameter sweeps across thousands of strategy variants. This project tests one specific strategy — the framework overhead isn't justified. |
| Backtest framework | Custom | NautilusTrader | If you need live trading or institutional-grade order modeling. This is backtest-only with simple market-order fills. |
| Backtest framework | Custom | Backtrader | Never. Slow (pure Python), abandoned by original author, shows strain at scale. |
| Timezone | zoneinfo | pytz | Never for new projects. pytz is legacy; Pandas is dropping it. zoneinfo is stdlib. |
| Data format | Parquet (converted) | Raw CSV | First run loads CSVs; subsequent runs use Parquet. Keep both — CSVs are the source of truth, Parquet is the performance cache. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Pandas as primary data engine | 5-30x slower than Polars for CSV reads, groupby, and filtering at 100M+ row scale. Memory-hungry — loads entire files before filtering. | Polars with lazy evaluation |
| Backtrader | Abandoned by original author. Pure Python — will crawl on 100M+ rows. Event-driven overhead is pointless for a single replay-style backtest. | Custom NumPy/Numba engine |
| pytz | Legacy. `zoneinfo` is stdlib since Python 3.9. pytz has DST edge cases that zoneinfo handles correctly. Pandas is dropping pytz support. | `zoneinfo` + `tzdata` |
| ta-lib / pandas-ta | Generic indicator libraries. VWAP, sigma bands, and volume profiles are simple cumulative math — 5-10 lines of NumPy. Adding a C-compiled ta-lib dependency for `cumsum(pv)/cumsum(v)` is absurd. | Direct NumPy computation |
| SQLite / database | The data is read-once, process-sequentially. There are no random-access queries. A database adds complexity with zero benefit. | Polars scan + Parquet cache |
| Matplotlib for results | Out of scope — the project outputs CSV/JSON. If visualization is added later, Plotly is better for interactive financial charts. | CSV/JSON output; Plotly if needed later |
| `decimal.Decimal` | NQ tick size is 0.25 points ($5/tick). IEEE 754 float64 has ~15 digits of precision. Rounding to tick boundaries is trivial: `round(price * 4) / 4`. Decimal would be 100x slower for zero practical benefit. | float64 with tick-rounding |

## Performance Considerations

### Data Scale

- **884 daily CSV files**, each ~15-22MB, ~150K rows → ~15GB raw, ~130M total rows
- After front-month filtering: ~60-70% of rows are front-month NQ → ~80-90M rows
- Each row is narrow (17 columns, mostly numeric) → ~2-4GB in memory after filtering

### Critical Optimizations

**1. Lazy CSV Scanning (Polars)**

```python
import polars as pl

lf = pl.scan_csv("path/to/day.csv")
    .filter(pl.col("symbol").str.starts_with("NQ"))  # Filter BEFORE loading
    .filter(~pl.col("symbol").str.contains("-"))      # Exclude spreads
    .collect()
```

This reads column headers, applies predicate pushdown, and only materializes matching rows. For a file with 150K rows where 50K are front-month NQ, you skip parsing 100K rows entirely.

**2. One-Time CSV → Parquet Conversion**

Convert all 884 CSVs to Parquet once. Subsequent backtest runs load Parquet files 5-10x faster with 3-5x smaller files. Parquet preserves types (no re-parsing timestamps on every load).

```python
for csv_path in csv_files:
    pl.scan_csv(csv_path).filter(...).sink_parquet(parquet_path)
```

**3. NumPy Cumsum for VWAP**

```python
import numpy as np

def compute_vwap(prices: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    cum_pv = np.cumsum(prices * volumes)
    cum_v = np.cumsum(volumes)
    return np.where(cum_v > 0, cum_pv / cum_v, np.nan)
```

This is O(n) with no loops, runs in microseconds for a single day (~50K rows), and is trivially parallelizable across days.

**4. Numba for the Event Loop**

The backtest event loop processes each bar sequentially (check signals, manage positions, track P&L). This can't be vectorized. Numba `@njit` compiles the loop to machine code:

```python
from numba import njit

@njit(cache=True)
def run_backtest(prices, vwap, sigma, ...) -> np.ndarray:
    # Process each bar: O(n) with compiled speed
    ...
```

Expect ~10-50x speedup over pure Python for the inner loop. With `cache=True`, the JIT compilation happens once and is reused.

**5. Memory Budget**

| Stage | Estimated Memory |
|-------|-----------------|
| Single day (front-month filtered) | ~5-15 MB |
| All days in memory (if needed) | ~2-4 GB |
| HTF volume profile (180-day rolling) | ~200-500 MB |
| Backtest state (positions, trades) | < 10 MB |
| **Total peak** | **~3-5 GB** |

This fits comfortably on any modern machine. No chunking or streaming required — load all front-month data into memory, process sequentially by day.

### Processing Architecture

```
Phase 1: Data Prep (run once)
  CSV files → Polars scan_csv → filter front-month → write Parquet

Phase 2: Load (each backtest run)
  Parquet files → Polars read_parquet → extract NumPy arrays

Phase 3: Compute (per session)
  NumPy arrays → VWAP, bands, volume profiles → session-level features

Phase 4: Backtest (sequential)
  Numba-compiled event loop → process each bar → trade signals → P&L

Phase 5: Output
  Trade log + metrics → Polars DataFrame → CSV/JSON
```

### Expected Performance

| Operation | Estimated Time |
|-----------|---------------|
| CSV→Parquet conversion (one-time) | 2-5 minutes |
| Load all Parquet files | 10-30 seconds |
| VWAP + bands for all sessions | 5-15 seconds |
| Volume profiles (daily + 180-day HTF) | 30-60 seconds |
| Full backtest (884 days) | 30-120 seconds |
| **Total per run (after conversion)** | **~1-4 minutes** |

## Data Pipeline Detail

### CSV Format (Databento CME MDP3 BBO)

The source CSVs have this structure:
```
ts_recv, ts_event, rtype, publisher_id, instrument_id, side, price, size,
flags, sequence, bid_px_00, ask_px_00, bid_sz_00, ask_sz_00,
bid_ct_00, ask_ct_00, symbol
```

Key parsing considerations:
- `ts_recv` and `ts_event` are nanosecond Unix timestamps → parse as `pl.Datetime("ns")`
- `side` is categorical: `B` (buy trade), `A` (ask/sell trade), `N` (no trade, BBO snapshot only)
- `price` and `size` are populated only when `side ∈ {B, A}` — otherwise use `bid_px_00`/`ask_px_00` for mid-price
- `symbol` contains mixed contracts (NQH4, NQM4, NQU4, NQZ4, spreads like NQH4-NQM4)

### Polars Schema Declaration

Declare types explicitly to avoid inference overhead on 884 files:

```python
SCHEMA = {
    "ts_recv": pl.UInt64,
    "ts_event": pl.UInt64,
    "rtype": pl.UInt8,
    "publisher_id": pl.UInt16,
    "instrument_id": pl.UInt32,
    "side": pl.Utf8,
    "price": pl.Float64,
    "size": pl.UInt32,
    "flags": pl.UInt8,
    "sequence": pl.UInt32,
    "bid_px_00": pl.Float64,
    "ask_px_00": pl.Float64,
    "bid_sz_00": pl.UInt32,
    "ask_sz_00": pl.UInt32,
    "bid_ct_00": pl.UInt16,
    "ask_ct_00": pl.UInt16,
    "symbol": pl.Utf8,
}
```

## Sources

- Polars v1.39.1 release: https://github.com/pola-rs/polars/releases/tag/py-1.39.1
- NumPy v2.4.4 release: https://github.com/numpy/numpy/releases/tag/v2.4.4
- Numba v0.65.0 release: https://pypi.org/project/numba/
- PyArrow v23.0.1 release: https://arrow.apache.org/release/23.0.1.html
- Pandas 3.0 PyArrow changes: https://medium.com/@kaniel-outis/pandas-3-0s-pyarrow-string-revolution
- Polars vs Pandas benchmarks (100M rows): https://tildalice.io/polars-vs-pandas-2026-benchmarks/
- Python 3.14 release schedule: https://peps.python.org/pep-0745/
- zoneinfo stdlib docs: https://docs.python.org/3.15/library/zoneinfo.html
- pytest v9.0.2: https://docs.pytest.org/en/stable/changelog.html
- Parquet vs CSV for quant trading: https://medium.com/balaena-quant-insights/replacing-the-csv-file-format-806c35e4125d
- VectorBT vs event-driven backtesting: https://python.financial/
- Databento Python SDK: https://github.com/databento/databento-python
