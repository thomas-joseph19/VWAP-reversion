"""Front-month contract selection helpers."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import polars as pl


EASTERN = ZoneInfo("America/New_York")
EASTERN_KEY = getattr(EASTERN, "key", "America/New_York")


def _ensure_eastern_timestamp(df: pl.DataFrame, timestamp_col: str) -> pl.DataFrame:
    dtype = df.schema.get(timestamp_col)
    if dtype is None:
        raise ValueError(f"Missing timestamp column: {timestamp_col}")

    if isinstance(dtype, pl.Datetime) and dtype.time_zone == EASTERN_KEY:
        return df.with_columns(pl.col(timestamp_col).alias("_ts_et"))

    if isinstance(dtype, pl.Datetime) and dtype.time_zone == "UTC":
        return df.with_columns(
            pl.col(timestamp_col).dt.convert_time_zone(EASTERN_KEY).alias("_ts_et")
        )

    return df.with_columns(
        pl.col(timestamp_col)
        .str.strptime(pl.Datetime("ns", "UTC"), strict=True)
        .dt.convert_time_zone(EASTERN_KEY)
        .alias("_ts_et")
    )


def _trading_date_expr(timestamp_col: str) -> pl.Expr:
    ts_col = pl.col(timestamp_col)
    after_globex_open = (
        (ts_col.dt.hour() > 18)
        | ((ts_col.dt.hour() == 18) & (ts_col.dt.minute() >= 0))
    )
    return (
        pl.when(after_globex_open)
        .then(ts_col.dt.date() + pl.duration(days=1))
        .otherwise(ts_col.dt.date())
        .alias("trading_date")
    )


def add_contract_trading_date(df: pl.DataFrame, timestamp_col: str = "ts_recv") -> pl.DataFrame:
    """Add ET-local timestamp and Globex trading-date columns."""

    enriched = _ensure_eastern_timestamp(df, timestamp_col).with_columns(
        _trading_date_expr("_ts_et")
    )
    return enriched.rename({"_ts_et": f"{timestamp_col}_et"})


def build_daily_contract_map(df: pl.DataFrame) -> pl.DataFrame:
    """Build a causal daily front-month map from outright trade volume."""

    enriched = add_contract_trading_date(df)
    eligible = enriched.filter(
        pl.col("symbol").str.starts_with("NQ")
        & ~pl.col("symbol").str.contains("-")
        & pl.col("side").is_in(["A", "B"])
    )
    volumes = (
        eligible.group_by(["trading_date", "symbol"])
        .agg(pl.col("size").sum().alias("trade_volume"))
        .sort(["trading_date", "trade_volume", "symbol"], descending=[False, True, False])
    )

    input_days = set(enriched["trading_date"].unique().to_list())
    eligible_days = set(volumes["trading_date"].unique().to_list()) if volumes.height else set()
    if missing_days := sorted(input_days - eligible_days):
        return pl.DataFrame(schema=volumes.schema)

    front_month = (
        volumes.group_by("trading_date")
        .first()
        .rename({"symbol": "front_symbol"})
        .sort("trading_date")
        .with_columns(pl.col("front_symbol").shift(1).alias("prior_symbol"))
        .with_columns(
            pl.when(pl.col("prior_symbol").is_null())
            .then(False)
            .otherwise(pl.col("front_symbol") != pl.col("prior_symbol"))
            .alias("is_roll")
        )
    )
    return front_month.select(
        "trading_date", "front_symbol", "trade_volume", "is_roll", "prior_symbol"
    )


def apply_contract_map(df: pl.DataFrame, contract_map: pl.DataFrame) -> pl.DataFrame:
    """Filter rows to the mapped front-month symbol for each trading date."""

    missing_days = sorted(
        set(df["trading_date"].unique().to_list()) - set(contract_map["trading_date"].unique().to_list())
    )
    if missing_days:
        raise ValueError(
            "Missing contract map for trading_date(s): "
            + ", ".join(str(day) for day in missing_days)
        )

    filtered = (
        df.join(contract_map, on="trading_date", how="inner")
        .filter(pl.col("symbol") == pl.col("front_symbol"))
    )
    return filtered

