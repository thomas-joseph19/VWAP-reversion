"""Completed-session volume profile helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

import polars as pl

from .structural_levels import _compute_session_levels, attach_prior_day_structural_levels
from .vwap import _require_columns


DEFAULT_BUCKET_SIZE = 0.25
DEFAULT_VALUE_AREA_FRACTION = 0.70
DEFAULT_HTF_LOOKBACK_SESSIONS = 180
DEFAULT_LVN_MIN_PROMINENCE_RATIO = 0.20
PHASE7_DAILY_ARTIFACT_NAME = "phase7_daily_profiles.parquet"
PHASE7_OVERNIGHT_ARTIFACT_NAME = "phase7_overnight_profiles.parquet"
PHASE7_HTF_ARTIFACT_NAME = "phase7_htf_profiles.parquet"
PHASE7_ENRICHED_ARTIFACT_NAME = "phase7_volume_profile_enriched.parquet"
VOLUME_PROFILE_VALIDATION_EXPORT_NAME = "volume_profile_validation_export.csv"
VOLUME_PROFILE_VALIDATION_MANIFEST_NAME = "validation_sessions.json"

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
_PHASE7_LEVEL_ORDER = (
    "prior_rth_poc",
    "prior_rth_vah",
    "prior_rth_val",
    "overnight_poc",
    "overnight_vah",
    "overnight_val",
    "htf_poc",
    "htf_vah",
    "htf_val",
    "htf_lvn_above",
    "htf_lvn_below",
)
_VALIDATION_COLUMNS = [
    "trading_date",
    "ts_recv_et",
    "prior_rth_poc",
    "prior_rth_vah",
    "prior_rth_val",
    "overnight_poc",
    "overnight_vah",
    "overnight_val",
    "htf_poc",
    "htf_vah",
    "htf_val",
    "htf_nearest_lvn_above",
    "htf_nearest_lvn_below",
    "phase7_nearest_structural_level",
    "phase7_nearest_structural_distance",
    "phase7_quality_status",
    "htf_source_session_count",
    "htf_roll_mixed_window",
]


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

    return _empty_profile_frame(
        rows,
        "trading_date",
        [
            "trading_date",
            "profile_family",
            "source_trading_date",
            "bucket_size",
            "bucket_prices",
            "bucket_volumes",
            "daily_rth_poc",
            "daily_rth_vah",
            "daily_rth_val",
            "prior_rth_poc",
            "prior_rth_vah",
            "prior_rth_val",
            "lvn_prices",
            "profile_trade_rows",
            "profile_total_volume",
            "quality_status",
            "front_symbol",
        ],
    )


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

    return _empty_profile_frame(
        rows,
        "trading_date",
        [
            "trading_date",
            "profile_family",
            "source_trading_date",
            "bucket_size",
            "bucket_prices",
            "bucket_volumes",
            "overnight_poc",
            "overnight_vah",
            "overnight_val",
            "lvn_prices",
            "profile_trade_rows",
            "profile_total_volume",
            "quality_status",
            "front_symbol",
        ],
    )


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


def _empty_profile_frame(
    rows: list[dict[str, object]],
    sort_column: str,
    columns: list[str] | None = None,
) -> pl.DataFrame:
    if not rows:
        if columns is None:
            return pl.DataFrame([], strict=False)
        return pl.DataFrame({column: [] for column in columns}, strict=False)
    return pl.DataFrame(rows, strict=False).sort(sort_column)


def _build_roll_boundary_deltas(sorted_profiles: pl.DataFrame) -> list[float]:
    deltas = [0.0] * sorted_profiles.height
    front_symbols = sorted_profiles["front_symbol"].to_list()
    current_daily_rth_poc = sorted_profiles["daily_rth_poc"].to_list()

    for idx in range(1, sorted_profiles.height):
        prior_symbol = front_symbols[idx - 1]
        current_symbol = front_symbols[idx]
        if prior_symbol is None or current_symbol is None or prior_symbol == current_symbol:
            continue

        prior_daily_rth_poc = current_daily_rth_poc[idx - 1]
        current_daily_rth_poc_value = current_daily_rth_poc[idx]
        if prior_daily_rth_poc is None or current_daily_rth_poc_value is None:
            continue
        deltas[idx] = float(current_daily_rth_poc_value) - float(prior_daily_rth_poc)

    return deltas


def _roll_shift_for_window(source_idx: int, target_idx: int, boundary_deltas: list[float]) -> float:
    if source_idx >= target_idx:
        return 0.0
    return float(sum(boundary_deltas[source_idx + 1 : target_idx + 1]))


def _aggregate_histograms_on_target_axis(
    sorted_profiles: pl.DataFrame,
    window: pl.DataFrame,
    *,
    target_idx: int,
    boundary_deltas: list[float],
) -> tuple[list[float], list[float], bool]:
    aggregated: dict[float, float] = {}
    roll_adjustment_applied = False
    source_indices = {
        trading_date_value: idx
        for idx, trading_date_value in enumerate(sorted_profiles["trading_date"].to_list())
    }

    for source_row in window.iter_rows(named=True):
        source_idx = source_indices[source_row["trading_date"]]
        price_shift = _roll_shift_for_window(source_idx, target_idx, boundary_deltas)
        if price_shift != 0.0:
            roll_adjustment_applied = True

        for price, volume in zip(
            source_row["bucket_prices"],
            source_row["bucket_volumes"],
            strict=True,
        ):
            shifted_price = _snap_price(float(price) + price_shift, float(source_row["bucket_size"]))
            aggregated[shifted_price] = aggregated.get(shifted_price, 0.0) + float(volume)

    bucket_prices = sorted(aggregated)
    return bucket_prices, [aggregated[price] for price in bucket_prices], roll_adjustment_applied


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
            "daily_rth_poc",
        },
    )
    sorted_profiles = daily_profiles.sort("trading_date")
    rows: list[dict[str, object]] = []
    all_dates = sorted_profiles["trading_date"].to_list()
    boundary_deltas = _build_roll_boundary_deltas(sorted_profiles)

    for idx, trading_date_value in enumerate(all_dates):
        window = sorted_profiles.slice(max(0, idx - lookback_sessions), min(idx, lookback_sessions))
        source_session_count = window.height
        source_front_symbols = sorted(
            symbol for symbol in set(window["front_symbol"].drop_nulls().to_list()) if symbol is not None
        )
        roll_anchor_symbol = sorted_profiles["front_symbol"][idx]
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
            "roll_adjustment_applied": False,
            "roll_anchor_symbol": None if roll_anchor_symbol is None else str(roll_anchor_symbol),
            "source_front_symbols": source_front_symbols,
            "quality_status": "insufficient_history",
        }

        if source_session_count == 0:
            rows.append(row)
            continue

        bucket_prices, bucket_volumes, roll_adjustment_applied = _aggregate_histograms_on_target_axis(
            sorted_profiles,
            window,
            target_idx=idx,
            boundary_deltas=boundary_deltas,
        )
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
                "roll_adjustment_applied": roll_adjustment_applied,
                "quality_status": quality_status,
            }
        )
        rows.append(row)

    return _empty_profile_frame(
        rows,
        "trading_date",
        [
            "trading_date",
            "profile_family",
            "window_start_date",
            "window_end_date",
            "bucket_size",
            "bucket_prices",
            "bucket_volumes",
            "htf_poc",
            "htf_vah",
            "htf_val",
            "lvn_prices",
            "source_session_count",
            "window_target_sessions",
            "window_complete",
            "roll_mixed_window",
            "roll_adjustment_applied",
            "roll_anchor_symbol",
            "source_front_symbols",
            "quality_status",
        ],
    )


def _pick_nearest_lvn_above(value: dict[str, object]) -> float | None:
    reference_price = value.get("phase7_reference_price")
    lvn_prices = value.get("lvn_prices")
    if reference_price is None or not isinstance(lvn_prices, list):
        return None

    candidates = sorted(float(price) for price in lvn_prices if price is not None and float(price) >= float(reference_price))
    if not candidates:
        return None
    return candidates[0]


def _pick_nearest_lvn_below(value: dict[str, object]) -> float | None:
    reference_price = value.get("phase7_reference_price")
    lvn_prices = value.get("lvn_prices")
    if reference_price is None or not isinstance(lvn_prices, list):
        return None

    candidates = sorted(
        (float(price) for price in lvn_prices if price is not None and float(price) <= float(reference_price)),
        reverse=True,
    )
    if not candidates:
        return None
    return candidates[0]


def _pick_phase7_nearest_level(value: dict[str, object]) -> dict[str, object]:
    candidates: list[tuple[str, float]] = []
    for idx, label in enumerate(_PHASE7_LEVEL_ORDER):
        distance = value.get(f"distance_to_{label}")
        if distance is None:
            continue
        candidates.append((label, abs(float(distance)), idx))

    if not candidates:
        return {"label": None, "distance": None}

    label, distance, _ = min(candidates, key=lambda item: (item[1], item[2]))
    return {"label": label, "distance": distance}


def attach_volume_profile_levels(
    df: pl.DataFrame,
    proximity_threshold_points: float = 10.0,
    bucket_size: float = DEFAULT_BUCKET_SIZE,
    htf_lookback_sessions: int = DEFAULT_HTF_LOOKBACK_SESSIONS,
) -> pl.DataFrame:
    """Attach active overnight and HTF profile references to the canonical row stream."""

    _require_columns(df, _REQUIRED_COLUMNS)

    enriched = attach_prior_day_structural_levels(
        df,
        proximity_threshold_points=proximity_threshold_points,
    )
    overnight_profiles = build_overnight_profiles(df, bucket_size=bucket_size).rename(
        {"quality_status": "overnight_quality_status"}
    )
    htf_profiles = build_htf_profiles(
        build_daily_rth_profiles(df, bucket_size=bucket_size),
        lookback_sessions=htf_lookback_sessions,
    ).rename(
        {
            "quality_status": "htf_quality_status",
            "source_session_count": "htf_source_session_count",
            "window_complete": "htf_window_complete",
            "roll_mixed_window": "htf_roll_mixed_window",
        }
    )

    bid_col = pl.col("bid_px_00") if "bid_px_00" in df.columns else pl.lit(None)
    ask_col = pl.col("ask_px_00") if "ask_px_00" in df.columns else pl.lit(None)
    phase7_reference_price = (
        pl.when(pl.col("side").is_in(_TRADE_SIDES))
        .then(pl.col("price"))
        .when(pl.all_horizontal(bid_col.is_not_null(), ask_col.is_not_null()))
        .then((bid_col + ask_col) / 2.0)
        .when(bid_col.is_not_null())
        .then(bid_col)
        .when(ask_col.is_not_null())
        .then(ask_col)
        .otherwise(None)
        .alias("phase7_reference_price")
    )

    joined = (
        enriched.with_row_index("__row")
        .join(
            overnight_profiles.select(
                "trading_date",
                "overnight_poc",
                "overnight_vah",
                "overnight_val",
                "overnight_quality_status",
            ),
            on="trading_date",
            how="left",
        )
        .join(
            htf_profiles.select(
                "trading_date",
                "htf_poc",
                "htf_vah",
                "htf_val",
                "lvn_prices",
                "htf_source_session_count",
                "htf_window_complete",
                "htf_roll_mixed_window",
                "htf_quality_status",
                "roll_adjustment_applied",
                "roll_anchor_symbol",
            ),
            on="trading_date",
            how="left",
        )
        .with_columns(phase7_reference_price)
    )

    joined = joined.with_columns(
        pl.struct("phase7_reference_price", "lvn_prices")
        .map_elements(_pick_nearest_lvn_above, return_dtype=pl.Float64)
        .alias("htf_nearest_lvn_above"),
        pl.struct("phase7_reference_price", "lvn_prices")
        .map_elements(_pick_nearest_lvn_below, return_dtype=pl.Float64)
        .alias("htf_nearest_lvn_below"),
    )

    for label in (
        "prior_rth_poc",
        "prior_rth_vah",
        "prior_rth_val",
        "overnight_poc",
        "overnight_vah",
        "overnight_val",
        "htf_poc",
        "htf_vah",
        "htf_val",
        "htf_lvn_above",
        "htf_lvn_below",
    ):
        source_column = label
        if label == "htf_lvn_above":
            source_column = "htf_nearest_lvn_above"
        elif label == "htf_lvn_below":
            source_column = "htf_nearest_lvn_below"

        joined = joined.with_columns(
            (pl.col("phase7_reference_price") - pl.col(source_column)).alias(f"distance_to_{label}")
        )

    joined = joined.with_columns(
        pl.when(pl.all_horizontal(pl.col("overnight_poc").is_not_null(), pl.col("htf_poc").is_not_null()))
        .then(pl.lit("ok"))
        .when(pl.all_horizontal(pl.col("overnight_poc").is_null(), pl.col("htf_poc").is_null()))
        .then(pl.lit("missing_both"))
        .when(pl.col("overnight_poc").is_null())
        .then(pl.lit("missing_overnight"))
        .otherwise(pl.lit("missing_htf"))
        .alias("phase7_quality_status")
    )

    nearest_struct = pl.struct(
        *[pl.col(f"distance_to_{label}").alias(f"distance_to_{label}") for label in _PHASE7_LEVEL_ORDER]
    ).map_elements(
        _pick_phase7_nearest_level,
        return_dtype=pl.Struct({"label": pl.Utf8, "distance": pl.Float64}),
    )

    threshold_terms = [
        pl.when(pl.col(f"distance_to_{label}").is_not_null())
        .then(pl.col(f"distance_to_{label}").abs() <= proximity_threshold_points)
        .otherwise(False)
        .cast(pl.Int64)
        for label in _PHASE7_LEVEL_ORDER
    ]

    return (
        joined.with_columns(nearest_struct.alias("__phase7_nearest"))
        .with_columns(
            pl.col("__phase7_nearest").struct.field("label").alias("phase7_nearest_structural_level"),
            pl.col("__phase7_nearest").struct.field("distance").alias("phase7_nearest_structural_distance"),
            sum(threshold_terms).alias("phase7_levels_within_threshold"),
        )
        .sort("__row")
        .drop("__row", "__phase7_nearest", "lvn_prices")
    )


def write_volume_profile_artifacts(
    df: pl.DataFrame,
    output_dir: Path,
    proximity_threshold_points: float = 10.0,
    bucket_size: float = DEFAULT_BUCKET_SIZE,
    htf_lookback_sessions: int = DEFAULT_HTF_LOOKBACK_SESSIONS,
) -> tuple[Path, Path, Path, Path]:
    """Persist deterministic Phase 7 profile-family and enriched artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    daily_profiles = build_daily_rth_profiles(df, bucket_size=bucket_size)
    overnight_profiles = build_overnight_profiles(df, bucket_size=bucket_size)
    htf_profiles = build_htf_profiles(
        daily_profiles,
        lookback_sessions=htf_lookback_sessions,
    )
    enriched = attach_volume_profile_levels(
        df,
        proximity_threshold_points=proximity_threshold_points,
        bucket_size=bucket_size,
        htf_lookback_sessions=htf_lookback_sessions,
    )

    daily_path = output_dir / PHASE7_DAILY_ARTIFACT_NAME
    overnight_path = output_dir / PHASE7_OVERNIGHT_ARTIFACT_NAME
    htf_path = output_dir / PHASE7_HTF_ARTIFACT_NAME
    enriched_path = output_dir / PHASE7_ENRICHED_ARTIFACT_NAME
    daily_profiles.write_parquet(daily_path)
    overnight_profiles.write_parquet(overnight_path)
    htf_profiles.write_parquet(htf_path)
    enriched.write_parquet(enriched_path)
    return daily_path, overnight_path, htf_path, enriched_path


def write_volume_profile_validation_export(
    enriched_df: pl.DataFrame,
    output_dir: Path,
    validation_dates: list[str],
    bucket_size: float = DEFAULT_BUCKET_SIZE,
    htf_lookback_sessions: int = DEFAULT_HTF_LOOKBACK_SESSIONS,
) -> None:
    """Write deterministic Phase 7 validation artifacts for selected sessions."""

    normalized_dates = sorted(dict.fromkeys(validation_dates))
    if not normalized_dates:
        raise ValueError("validation_dates must include at least one YYYY-MM-DD value")

    _require_columns(enriched_df, set(_VALIDATION_COLUMNS))

    output_dir.mkdir(parents=True, exist_ok=True)
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    comparison = (
        enriched_df.with_columns(pl.col("trading_date").cast(pl.Utf8))
        .filter(pl.col("trading_date").is_in(normalized_dates))
        .sort(["trading_date", "ts_recv_et"])
        .select(_VALIDATION_COLUMNS)
    )
    comparison.write_csv(validation_dir / VOLUME_PROFILE_VALIDATION_EXPORT_NAME)

    manifest = {
        "validation_dates": normalized_dates,
        "bucket_size": bucket_size,
        "htf_lookback_sessions": htf_lookback_sessions,
        "daily_artifact": PHASE7_DAILY_ARTIFACT_NAME,
        "overnight_artifact": PHASE7_OVERNIGHT_ARTIFACT_NAME,
        "htf_artifact": PHASE7_HTF_ARTIFACT_NAME,
        "enriched_artifact": PHASE7_ENRICHED_ARTIFACT_NAME,
        "validation_export": f"validation/{VOLUME_PROFILE_VALIDATION_EXPORT_NAME}",
        "row_count": comparison.height,
    }
    (validation_dir / VOLUME_PROFILE_VALIDATION_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
