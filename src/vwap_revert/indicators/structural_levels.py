"""Prior-day structural level helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import polars as pl

from .vwap import _require_columns


_REQUIRED_COLUMNS = {"trading_date", "ts_recv", "is_rth", "side", "price", "size"}
_TRADE_SIDES = ("A", "B")
_LEVEL_COLUMNS = ["prior_rth_vah", "prior_rth_val", "prior_rth_poc"]
_QUALITY_MISSING = "missing_prior_session"
_QUALITY_UNUSABLE = "unusable_prior_session"
_QUALITY_OK = "ok"


@dataclass(frozen=True)
class _ProfileLevels:
    poc: float
    vah: float
    val: float
    trade_rows: int
    total_volume: float


def _trade_rows(df: pl.DataFrame) -> pl.DataFrame:
    _require_columns(df, _REQUIRED_COLUMNS)
    return df.filter(pl.col("is_rth") & pl.col("side").is_in(_TRADE_SIDES)).sort(["trading_date", "ts_recv"])


def _compute_session_levels(session_rows: pl.DataFrame) -> _ProfileLevels | None:
    trade_rows = session_rows.height
    if trade_rows == 0:
        return None

    volume_by_price = (
        session_rows.group_by("price")
        .agg(pl.col("size").sum().alias("volume"))
        .sort("price")
    )
    total_volume = float(volume_by_price["volume"].sum())
    if total_volume <= 0.0:
        return None

    session_vwap = float((session_rows["price"] * session_rows["size"]).sum() / total_volume)
    poc_row = (
        volume_by_price.with_columns(
            (pl.col("price") - session_vwap).abs().alias("distance_to_vwap"),
        )
        .sort(["volume", "distance_to_vwap", "price"], descending=[True, False, False])
        .row(0, named=True)
    )
    poc_price = float(poc_row["price"])
    prices = volume_by_price["price"].to_list()
    volumes = volume_by_price["volume"].to_list()
    poc_index = prices.index(poc_price)

    lower_index = poc_index
    upper_index = poc_index
    accumulated_volume = float(volumes[poc_index])
    target_volume = total_volume * 0.7

    while accumulated_volume < target_volume and (lower_index > 0 or upper_index < len(prices) - 1):
        left_index = lower_index - 1 if lower_index > 0 else None
        right_index = upper_index + 1 if upper_index < len(prices) - 1 else None

        if left_index is None:
            next_index = right_index
        elif right_index is None:
            next_index = left_index
        else:
            left_volume = float(volumes[left_index])
            right_volume = float(volumes[right_index])
            if left_volume >= right_volume:
                next_index = left_index
            else:
                next_index = right_index

        accumulated_volume += float(volumes[next_index])
        lower_index = min(lower_index, next_index)
        upper_index = max(upper_index, next_index)

    return _ProfileLevels(
        poc=poc_price,
        vah=float(prices[upper_index]),
        val=float(prices[lower_index]),
        trade_rows=trade_rows,
        total_volume=total_volume,
    )


def compute_prior_day_structural_levels(df: pl.DataFrame) -> pl.DataFrame:
    """Compute prior-day RTH value-area levels keyed by current trading date."""

    _require_columns(df, _REQUIRED_COLUMNS)

    unique_dates = sorted(df["trading_date"].unique().to_list())
    session_levels: dict[object, _ProfileLevels | None] = {}
    trade_rows = _trade_rows(df)

    for trading_date in unique_dates:
        session_levels[trading_date] = _compute_session_levels(
            trade_rows.filter(pl.col("trading_date") == trading_date)
        )

    rows: list[dict[str, object]] = []
    available_dates = set(unique_dates)

    for trading_date in unique_dates:
        source_trading_date = trading_date - timedelta(days=1)
        levels = session_levels.get(source_trading_date)

        if source_trading_date not in available_dates:
            rows.append(
                {
                    "trading_date": trading_date,
                    "source_trading_date": source_trading_date,
                    "prior_rth_vah": None,
                    "prior_rth_val": None,
                    "prior_rth_poc": None,
                    "levels_available": False,
                    "quality_status": _QUALITY_MISSING,
                    "profile_trade_rows": 0,
                    "profile_total_volume": 0.0,
                }
            )
            continue

        if levels is None:
            rows.append(
                {
                    "trading_date": trading_date,
                    "source_trading_date": source_trading_date,
                    "prior_rth_vah": None,
                    "prior_rth_val": None,
                    "prior_rth_poc": None,
                    "levels_available": False,
                    "quality_status": _QUALITY_UNUSABLE,
                    "profile_trade_rows": 0,
                    "profile_total_volume": 0.0,
                }
            )
            continue

        rows.append(
            {
                "trading_date": trading_date,
                "source_trading_date": source_trading_date,
                "prior_rth_vah": levels.vah,
                "prior_rth_val": levels.val,
                "prior_rth_poc": levels.poc,
                "levels_available": True,
                "quality_status": _QUALITY_OK,
                "profile_trade_rows": levels.trade_rows,
                "profile_total_volume": levels.total_volume,
            }
        )

    return pl.DataFrame(rows).sort("trading_date")


def attach_prior_day_structural_levels(df: pl.DataFrame, proximity_threshold_points: float = 10.0) -> pl.DataFrame:
    """Attach prior-day structural levels and proximity features to the full row stream."""

    _require_columns(df, _REQUIRED_COLUMNS)
    session_levels = compute_prior_day_structural_levels(df)

    bid_col = pl.col("bid_px_00") if "bid_px_00" in df.columns else pl.lit(None)
    ask_col = pl.col("ask_px_00") if "ask_px_00" in df.columns else pl.lit(None)
    reference_price = (
        pl.when(pl.col("side").is_in(_TRADE_SIDES))
        .then(pl.col("price"))
        .when(pl.all_horizontal(bid_col.is_not_null(), ask_col.is_not_null()))
        .then((bid_col + ask_col) / 2.0)
        .when(bid_col.is_not_null())
        .then(bid_col)
        .when(ask_col.is_not_null())
        .then(ask_col)
        .otherwise(None)
        .alias("structural_reference_price")
    )

    base = df.with_row_index("__row")
    enriched = base.join(session_levels, on="trading_date", how="left").with_columns(reference_price)

    for level_column in _LEVEL_COLUMNS:
        distance_column = f"distance_to_{level_column}"
        near_column = f"near_{level_column}"
        enriched = enriched.with_columns(
            (pl.col("structural_reference_price") - pl.col(level_column)).alias(distance_column)
        ).with_columns(
            pl.when(pl.col(distance_column).is_not_null())
            .then(pl.col(distance_column).abs() <= proximity_threshold_points)
            .otherwise(False)
            .alias(near_column)
        )

    distance_pairs = [
        ("prior_rth_vah", "distance_to_prior_rth_vah"),
        ("prior_rth_val", "distance_to_prior_rth_val"),
        ("prior_rth_poc", "distance_to_prior_rth_poc"),
    ]
    nearest_struct = pl.struct(
        *[
            pl.struct(
                pl.lit(level_name).alias("label"),
                pl.col(distance_name).abs().alias("distance"),
            ).alias(f"{level_name}_candidate")
            for level_name, distance_name in distance_pairs
        ]
    ).map_elements(
        _pick_nearest_level,
        return_dtype=pl.Struct({"label": pl.Utf8, "distance": pl.Float64}),
    )

    return (
        enriched.with_columns(nearest_struct.alias("__nearest"))
        .with_columns(
            pl.col("__nearest").struct.field("label").alias("nearest_structural_level"),
            pl.col("__nearest").struct.field("distance").alias("nearest_structural_distance"),
            (
                pl.col("near_prior_rth_vah").cast(pl.Int64)
                + pl.col("near_prior_rth_val").cast(pl.Int64)
                + pl.col("near_prior_rth_poc").cast(pl.Int64)
            ).alias("structural_levels_within_threshold"),
        )
        .sort("__row")
        .drop("__row", "__nearest")
    )


def _pick_nearest_level(value: dict[str, dict[str, float | str | None]]) -> dict[str, float | str | None]:
    candidates: list[tuple[str, float]] = []
    order = {"prior_rth_vah": 0, "prior_rth_val": 1, "prior_rth_poc": 2}
    for candidate in value.values():
        label = candidate["label"]
        distance = candidate["distance"]
        if distance is not None:
            candidates.append((label, float(distance)))

    if not candidates:
        return {"label": None, "distance": None}

    label, distance = min(candidates, key=lambda item: (item[1], order[item[0]]))
    return {"label": label, "distance": distance}
