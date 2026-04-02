"""Timezone conversion and session labeling."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import polars as pl


EASTERN = ZoneInfo("America/New_York")
EASTERN_KEY = getattr(EASTERN, "key", "America/New_York")


def _as_eastern_expr(timestamp_col: str) -> pl.Expr:
    return pl.col(timestamp_col).dt.convert_time_zone(EASTERN_KEY)


def add_eastern_timestamps(df: pl.DataFrame, timestamp_col: str = "ts_recv") -> pl.DataFrame:
    """Persist ET-local timestamps for downstream session logic."""

    return df.with_columns(_as_eastern_expr(timestamp_col).alias(f"{timestamp_col}_et"))


def label_sessions(df: pl.DataFrame) -> pl.DataFrame:
    """Label rows with trading_date and Globex session flags."""

    if "ts_recv_et" not in df.columns:
        df = add_eastern_timestamps(df)

    ts_col = pl.col("ts_recv_et")
    session_name = (
        pl.when(ts_col.dt.hour() == 17)
        .then(pl.lit("maintenance"))
        .when(
            (ts_col.dt.hour() >= 18)
            | (ts_col.dt.hour() < 9)
            | ((ts_col.dt.hour() == 9) & (ts_col.dt.minute() < 30))
        )
        .then(pl.lit("overnight"))
        .otherwise(pl.lit("rth"))
        .alias("session_name")
    )
    trading_date = (
        pl.when(ts_col.dt.hour() >= 18)
        .then(ts_col.dt.date() + pl.duration(days=1))
        .otherwise(ts_col.dt.date())
        .alias("trading_date")
    )
    return df.with_columns(
        trading_date,
        session_name,
    ).with_columns(
        (pl.col("session_name") == "overnight").alias("is_overnight"),
        (pl.col("session_name") == "rth").alias("is_rth"),
        (pl.col("session_name") == "maintenance").alias("is_maintenance"),
    )

