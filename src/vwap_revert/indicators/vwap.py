"""Daily VWAP indicator helpers."""

from __future__ import annotations

import polars as pl


_REQUIRED_COLUMNS = {"trading_date", "ts_recv", "is_rth", "side", "price", "size"}
_TRADE_SIDES = ("A", "B")


def _require_columns(df: pl.DataFrame, required: set[str]) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def _trade_rows(df: pl.DataFrame) -> pl.DataFrame:
    _require_columns(df, _REQUIRED_COLUMNS)
    return (
        df.filter(pl.col("is_rth") & pl.col("side").is_in(_TRADE_SIDES))
        .sort(["trading_date", "ts_recv"])
        .with_columns((pl.col("price") * pl.col("size")).alias("notional"))
    )


def compute_daily_vwap(df: pl.DataFrame) -> pl.DataFrame:
    """Compute daily RTH VWAP for actual trade rows only."""

    trade_rows = _trade_rows(df)
    return trade_rows.with_columns(
        pl.col("notional").cum_sum().over("trading_date").alias("cum_notional"),
        pl.col("size").cum_sum().over("trading_date").alias("cum_volume"),
    ).with_columns((pl.col("cum_notional") / pl.col("cum_volume")).alias("daily_vwap"))
