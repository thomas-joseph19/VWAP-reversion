"""Completed-session volume profile helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from .structural_levels import _compute_session_levels
from .vwap import _require_columns


DEFAULT_BUCKET_SIZE = 0.25
DEFAULT_VALUE_AREA_FRACTION = 0.70
DEFAULT_HTF_LOOKBACK_SESSIONS = 180
DEFAULT_LVN_MIN_PROMINENCE_RATIO = 0.20

_REQUIRED_COLUMNS = {
    "trading_date",
    "ts_recv",
    "is_overnight",
    "is_rth",
    "side",
    "price",
    "size",
    "front_symbol",
}
_TRADE_SIDES = ("A", "B")
_LVN_KERNEL = (0.25, 0.5, 0.25)


@dataclass(frozen=True)
class _ProfileSummary:
    trading_date: date
    bucket_size: float
    bucket_prices: list[float]
    bucket_volumes: list[float]
    poc: float | None
    vah: float | None
    val: float | None
    lvn_prices: list[float]
    profile_trade_rows: int
    profile_total_volume: float
    quality_status: str
    front_symbol: str | None


def _trade_rows(df: pl.DataFrame, session_column: str) -> pl.DataFrame:
    _require_columns(df, _REQUIRED_COLUMNS)
    return df.filter(pl.col(session_column) & pl.col("side").is_in(_TRADE_SIDES)).sort(
        ["trading_date", "ts_recv"]
    )


def _snap_price(price: float, bucket_size: float) -> float:
    return round(price / bucket_size) * bucket_size


def _smoothed_volumes(volumes: list[float]) -> list[float]:
    if not volumes:
        return []
    if len(volumes) == 1:
        return [float(volumes[0])]

    smoothed: list[float] = []
    for idx, center in enumerate(volumes):
        left = volumes[idx - 1] if idx > 0 else center
        right = volumes[idx + 1] if idx < len(volumes) - 1 else center
        smoothed.append(
            (left * _LVN_KERNEL[0]) + (center * _LVN_KERNEL[1]) + (right * _LVN_KERNEL[2])
        )
    return smoothed


def detect_lvn_prices(
    bucket_prices: list[float],
    bucket_volumes: list[float],
    min_prominence_ratio: float = DEFAULT_LVN_MIN_PROMINENCE_RATIO,
) -> list[float]:
    """Return stable LVN bucket prices from a completed histogram."""

    if len(bucket_prices) != len(bucket_volumes):
        raise ValueError("bucket_prices and bucket_volumes must be the same length")
    if len(bucket_prices) < 3:
        return []

    smoothed = _smoothed_volumes([float(volume) for volume in bucket_volumes])
    prominence_threshold = max(float(volume) for volume in bucket_volumes) * min_prominence_ratio
    nodes: list[float] = []

    for idx in range(1, len(bucket_prices) - 1):
        raw_center = float(bucket_volumes[idx])
        raw_left = float(bucket_volumes[idx - 1])
        raw_right = float(bucket_volumes[idx + 1])
        if not (raw_center < raw_left and raw_center < raw_right):
            continue

        smooth_center = smoothed[idx]
        if not (smooth_center < smoothed[idx - 1] and smooth_center < smoothed[idx + 1]):
            continue

        prominence = min(raw_left, raw_right) - raw_center
        if prominence >= prominence_threshold:
            nodes.append(float(bucket_prices[idx]))

    return nodes


def _build_session_summary(
    session_rows: pl.DataFrame,
    *,
    bucket_size: float,
    poc_column: str,
    vah_column: str,
    val_column: str,
) -> _ProfileSummary:
    if session_rows.height == 0:
        return _ProfileSummary(
            trading_date=date.min,
            bucket_size=bucket_size,
            bucket_prices=[],
            bucket_volumes=[],
            poc=None,
            vah=None,
            val=None,
            lvn_prices=[],
            profile_trade_rows=0,
            profile_total_volume=0.0,
            quality_status="no_trade_rows",
            front_symbol=None,
        )

    trading_date_value = session_rows["trading_date"][0]
    front_symbol = session_rows["front_symbol"][0]
    histogram = (
        session_rows.with_columns(
            pl.col("price")
            .map_elements(lambda value: _snap_price(float(value), bucket_size), return_dtype=pl.Float64)
            .alias("bucket_price")
        )
        .group_by("bucket_price")
        .agg(pl.col("size").sum().alias("volume"))
        .sort("bucket_price")
    )
    bucket_prices = [float(value) for value in histogram["bucket_price"].to_list()]
    bucket_volumes = [float(value) for value in histogram["volume"].to_list()]
    profile_levels = _compute_session_levels(
        histogram.rename({"bucket_price": "price", "volume": "size"}).with_columns(
            pl.lit(trading_date_value).alias("trading_date"),
            pl.lit(True).alias("is_rth"),
            pl.lit("A").alias("side"),
            pl.datetime(2000, 1, 1).alias("ts_recv"),
        )
    )
    lvn_prices = detect_lvn_prices(bucket_prices, bucket_volumes)

    return _ProfileSummary(
        trading_date=trading_date_value,
        bucket_size=bucket_size,
        bucket_prices=bucket_prices,
        bucket_volumes=bucket_volumes,
        poc=None if profile_levels is None else float(profile_levels.poc),
        vah=None if profile_levels is None else float(profile_levels.vah),
        val=None if profile_levels is None else float(profile_levels.val),
        lvn_prices=lvn_prices,
        profile_trade_rows=session_rows.height,
        profile_total_volume=float(sum(bucket_volumes)),
        quality_status="ok" if profile_levels is not None else "no_trade_rows",
        front_symbol=None if front_symbol is None else str(front_symbol),
    )


def build_daily_rth_profiles(
    df: pl.DataFrame,
    bucket_size: float = DEFAULT_BUCKET_SIZE,
) -> pl.DataFrame:
    """Build one completed RTH profile row per trading date."""

    trade_rows = _trade_rows(df, "is_rth")
    rows: list[dict[str, object]] = []
    prior_levels: dict[str, float | None] = {
        "prior_rth_poc": None,
        "prior_rth_vah": None,
        "prior_rth_val": None,
    }

    for trading_date_value in sorted(trade_rows["trading_date"].unique().to_list()):
        session_rows = trade_rows.filter(pl.col("trading_date") == trading_date_value)
        summary = _build_session_summary(
            session_rows,
            bucket_size=bucket_size,
            poc_column="daily_rth_poc",
            vah_column="daily_rth_vah",
            val_column="daily_rth_val",
        )
        rows.append(
            {
                "trading_date": trading_date_value,
                "profile_family": "daily_rth",
                "source_trading_date": trading_date_value,
                "bucket_size": summary.bucket_size,
                "bucket_prices": summary.bucket_prices,
                "bucket_volumes": summary.bucket_volumes,
                "daily_rth_poc": summary.poc,
                "daily_rth_vah": summary.vah,
                "daily_rth_val": summary.val,
                **prior_levels,
                "lvn_prices": summary.lvn_prices,
                "profile_trade_rows": summary.profile_trade_rows,
                "profile_total_volume": summary.profile_total_volume,
                "quality_status": summary.quality_status,
                "front_symbol": summary.front_symbol,
            }
        )
        prior_levels = {
            "prior_rth_poc": summary.poc,
            "prior_rth_vah": summary.vah,
            "prior_rth_val": summary.val,
        }

    return pl.DataFrame(rows, strict=False).sort("trading_date")


def build_overnight_profiles(
    df: pl.DataFrame,
    bucket_size: float = DEFAULT_BUCKET_SIZE,
) -> pl.DataFrame:
    """Build same-day completed overnight profiles keyed by trading date."""

    trade_rows = _trade_rows(df, "is_overnight")
    rows: list[dict[str, object]] = []

    for trading_date_value in sorted(trade_rows["trading_date"].unique().to_list()):
        session_rows = trade_rows.filter(pl.col("trading_date") == trading_date_value)
        summary = _build_session_summary(
            session_rows,
            bucket_size=bucket_size,
            poc_column="overnight_poc",
            vah_column="overnight_vah",
            val_column="overnight_val",
        )
        rows.append(
            {
                "trading_date": trading_date_value,
                "profile_family": "overnight",
                "source_trading_date": trading_date_value,
                "bucket_size": summary.bucket_size,
                "bucket_prices": summary.bucket_prices,
                "bucket_volumes": summary.bucket_volumes,
                "overnight_poc": summary.poc,
                "overnight_vah": summary.vah,
                "overnight_val": summary.val,
                "lvn_prices": summary.lvn_prices,
                "profile_trade_rows": summary.profile_trade_rows,
                "profile_total_volume": summary.profile_total_volume,
                "quality_status": summary.quality_status,
                "front_symbol": summary.front_symbol,
            }
        )

    return pl.DataFrame(rows, strict=False).sort("trading_date")


def _aggregate_histograms(window: pl.DataFrame) -> tuple[list[float], list[float]]:
    aggregated: dict[float, float] = {}
    for prices, volumes in zip(
        window["bucket_prices"].to_list(),
        window["bucket_volumes"].to_list(),
        strict=True,
    ):
        for price, volume in zip(prices, volumes, strict=True):
            aggregated[float(price)] = aggregated.get(float(price), 0.0) + float(volume)

    bucket_prices = sorted(aggregated)
    return bucket_prices, [aggregated[price] for price in bucket_prices]


def build_htf_profiles(
    daily_profiles: pl.DataFrame,
    lookback_sessions: int = DEFAULT_HTF_LOOKBACK_SESSIONS,
    min_full_window_sessions: int = 20,
) -> pl.DataFrame:
    """Build causal HTF composites from strictly prior daily profiles."""

    _require_columns(
        daily_profiles,
        {
            "trading_date",
            "bucket_size",
            "bucket_prices",
            "bucket_volumes",
            "front_symbol",
        },
    )
    sorted_profiles = daily_profiles.sort("trading_date")
    rows: list[dict[str, object]] = []
    all_dates = sorted_profiles["trading_date"].to_list()

    for idx, trading_date_value in enumerate(all_dates):
        window = sorted_profiles.slice(max(0, idx - lookback_sessions), min(idx, lookback_sessions))
        source_session_count = window.height
        source_front_symbols = sorted(
            symbol for symbol in set(window["front_symbol"].drop_nulls().to_list()) if symbol is not None
        )
        roll_mixed_window = len(source_front_symbols) > 1
        window_complete = source_session_count == lookback_sessions
        bucket_size = (
            float(sorted_profiles["bucket_size"][idx])
            if "bucket_size" in sorted_profiles.columns and sorted_profiles.height
            else DEFAULT_BUCKET_SIZE
        )

        row: dict[str, object] = {
            "trading_date": trading_date_value,
            "profile_family": "htf_180d",
            "window_start_date": None if source_session_count == 0 else window["trading_date"][0],
            "window_end_date": None if source_session_count == 0 else window["trading_date"][-1],
            "bucket_size": bucket_size,
            "bucket_prices": [],
            "bucket_volumes": [],
            "htf_poc": None,
            "htf_vah": None,
            "htf_val": None,
            "lvn_prices": [],
            "source_session_count": source_session_count,
            "window_target_sessions": lookback_sessions,
            "window_complete": window_complete,
            "roll_mixed_window": roll_mixed_window,
            "source_front_symbols": source_front_symbols,
            "quality_status": "mixed_roll_window" if roll_mixed_window else "insufficient_history",
        }

        if source_session_count == 0:
            rows.append(row)
            continue

        if roll_mixed_window:
            rows.append(row)
            continue

        bucket_prices, bucket_volumes = _aggregate_histograms(window)
        profile_levels = _compute_session_levels(
            pl.DataFrame(
                {
                    "trading_date": [trading_date_value] * len(bucket_prices),
                    "ts_recv": [None] * len(bucket_prices),
                    "is_rth": [True] * len(bucket_prices),
                    "side": ["A"] * len(bucket_prices),
                    "price": bucket_prices,
                    "size": bucket_volumes,
                },
                strict=False,
            )
        )

        if source_session_count < min_full_window_sessions:
            quality_status = "insufficient_history"
        elif source_session_count < lookback_sessions:
            quality_status = "partial_window"
        else:
            quality_status = "full_window"

        row.update(
            {
                "bucket_prices": bucket_prices,
                "bucket_volumes": bucket_volumes,
                "htf_poc": None if profile_levels is None else float(profile_levels.poc),
                "htf_vah": None if profile_levels is None else float(profile_levels.vah),
                "htf_val": None if profile_levels is None else float(profile_levels.val),
                "lvn_prices": detect_lvn_prices(bucket_prices, bucket_volumes),
                "quality_status": quality_status,
            }
        )
        rows.append(row)

    return pl.DataFrame(rows, strict=False).sort("trading_date")
