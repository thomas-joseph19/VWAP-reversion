"""Schema and validation helpers for Databento CSV inputs."""

from __future__ import annotations

import polars as pl


RAW_SCHEMA = {
    "ts_recv": pl.String,
    "ts_event": pl.String,
    "rtype": pl.Int64,
    "publisher_id": pl.Int64,
    "instrument_id": pl.Int64,
    "side": pl.String,
    "price": pl.Float64,
    "size": pl.Float64,
    "flags": pl.Int64,
    "sequence": pl.Int64,
    "bid_px_00": pl.Float64,
    "ask_px_00": pl.Float64,
    "bid_sz_00": pl.Float64,
    "ask_sz_00": pl.Float64,
    "bid_ct_00": pl.Int64,
    "ask_ct_00": pl.Int64,
    "symbol": pl.String,
}

REQUIRED_COLUMNS = list(RAW_SCHEMA.keys())


def validate_required_columns(columns: list[str]) -> None:
    """Fail fast when required input columns are missing."""

    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        missing_columns = ", ".join(sorted(missing))
        raise ValueError(f"Missing required columns: {missing_columns}")


def parse_timestamp_column(expr: pl.Expr, column_name: str) -> pl.Expr:
    """Parse a raw UTC nanosecond timestamp string without silently coercing failures."""

    return (
        expr.str.strptime(pl.Datetime("ns", "UTC"), strict=True)
        .alias(column_name)
    )

