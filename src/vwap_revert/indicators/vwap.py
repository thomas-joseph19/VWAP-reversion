"""Daily VWAP indicator helpers."""

from __future__ import annotations

import polars as pl


_REQUIRED_COLUMNS = {"trading_date", "ts_recv", "is_rth", "side", "price", "size"}
_TRADE_SIDES = ("A", "B")
_BAND_COLUMNS = [
    "daily_vwap",
    "daily_sigma",
    "daily_vwap_upper_1s",
    "daily_vwap_lower_1s",
    "daily_vwap_upper_2s",
    "daily_vwap_lower_2s",
    "daily_vwap_upper_3s",
    "daily_vwap_lower_3s",
    "daily_vwap_upper_4s",
    "daily_vwap_lower_4s",
]


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

    return _with_vwap_columns(_trade_rows(df))


def _with_vwap_columns(trade_rows: pl.DataFrame) -> pl.DataFrame:
    return trade_rows.with_columns(
        pl.col("notional").cum_sum().over("trading_date").alias("cum_notional"),
        pl.col("size").cum_sum().over("trading_date").alias("cum_volume"),
    ).with_columns((pl.col("cum_notional") / pl.col("cum_volume")).alias("daily_vwap"))


def attach_daily_vwap_bands(df: pl.DataFrame) -> pl.DataFrame:
    """Attach daily VWAP band columns to the full session frame."""

    _require_columns(df, _REQUIRED_COLUMNS)
    trade_rows = _with_vwap_columns(_trade_rows(df)).with_columns(
        ((pl.col("price") ** 2) * pl.col("size")).alias("sq_notional")
    )
    indicator_rows = trade_rows.with_columns(
        pl.col("sq_notional").cum_sum().over("trading_date").alias("cum_sq_notional")
    ).with_columns(
        (
            (pl.col("cum_sq_notional") / pl.col("cum_volume")) - (pl.col("daily_vwap") ** 2)
        ).clip(lower_bound=0.0).sqrt().alias("daily_sigma")
    )

    for sigma in range(1, 5):
        indicator_rows = indicator_rows.with_columns(
            (pl.col("daily_vwap") + (pl.col("daily_sigma") * sigma)).alias(f"daily_vwap_upper_{sigma}s"),
            (pl.col("daily_vwap") - (pl.col("daily_sigma") * sigma)).alias(f"daily_vwap_lower_{sigma}s"),
        )

    base = df.with_row_index("__row")
    enriched = base.join(
        indicator_rows.select(["trading_date", "ts_recv", "cum_volume", "cum_notional", "cum_sq_notional", *_BAND_COLUMNS]),
        on=["trading_date", "ts_recv"],
        how="left",
    ).sort(["trading_date", "ts_recv", "__row"])

    return (
        enriched.with_columns(*(pl.col(column).forward_fill().over("trading_date") for column in _BAND_COLUMNS))
        .sort("__row")
        .drop("__row")
    )
