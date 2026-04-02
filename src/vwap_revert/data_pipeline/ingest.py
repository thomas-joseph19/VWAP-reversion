"""Typed raw-ingestion entrypoints."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from .schema import RAW_SCHEMA, parse_timestamp_column, validate_required_columns


def _require_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"CSV path does not exist: {path}")


def scan_raw_csv(path: Path) -> pl.LazyFrame:
    """Scan one raw Databento CSV with fail-fast validation."""

    _require_path(path)
    frame = pl.read_csv(path, schema=RAW_SCHEMA)
    validate_required_columns(frame.columns)

    return frame.lazy().with_columns(
        parse_timestamp_column(pl.col("ts_recv"), "ts_recv"),
        pl.when(pl.col("ts_event").str.len_chars() == 0)
        .then(None)
        .otherwise(parse_timestamp_column(pl.col("ts_event"), "ts_event"))
        .alias("ts_event"),
    )


def scan_candidate_outrights(path: Path) -> pl.LazyFrame:
    """Return outright NQ rows only."""

    return scan_raw_csv(path).filter(
        pl.col("symbol").str.starts_with("NQ") & ~pl.col("symbol").str.contains("-")
    )


def collect_sample_day(path: Path) -> pl.DataFrame:
    """Materialize one sample day for tests and smoke checks."""

    return scan_candidate_outrights(path).collect()

