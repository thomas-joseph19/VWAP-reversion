"""Phase 04 setup detection helpers."""

from __future__ import annotations

from datetime import time
import json
from pathlib import Path

import polars as pl

from .vwap import _require_columns


_REQUIRED_COLUMNS = {
    "trading_date",
    "ts_recv",
    "ts_recv_et",
    "daily_vwap",
    "daily_sigma",
    "structural_reference_price",
    "structural_levels_within_threshold",
    "nearest_structural_level",
    "nearest_structural_distance",
    "weekly_vwap",
    "monthly_vwap",
    "regime_label",
    "regime_min_sigma",
    "regime_max_sigma",
}
_ENRICHED_ARTIFACT_NAME = "phase4_setup_enriched.parquet"
_SETUP_LOG_ARTIFACT_NAME = "phase4_setup_log.parquet"
_VALIDATION_EXPORT_NAME = "setup_validation_export.csv"
_VALIDATION_MANIFEST_NAME = "validation_sessions.json"
_VALIDATION_COLUMNS = [
    "trading_date",
    "ts_recv_et",
    "structural_reference_price",
    "daily_vwap",
    "daily_sigma",
    "setup_sigma_signed",
    "time_window_passes",
    "vwap_extension_passes",
    "structural_confluence_passes",
    "setup_candidate_passes",
    "setup_event_emitted",
    "setup_direction",
    "nearest_structural_level",
    "nearest_structural_distance",
    "structural_levels_within_threshold",
    "confluence_score",
    "rejection_confirmed",
    "seconds_since_extreme",
    "rejection_displacement",
    "bid_px_00",
    "ask_px_00",
]


def attach_setup_detection_features(
    df: pl.DataFrame,
    window_start: time = time(9, 30),
    window_end: time = time(11, 30),
    min_sigma: float = 1.7,
    max_sigma: float = 3.0,
) -> pl.DataFrame:
    """Attach Phase 04 row-level setup-detection columns."""

    _require_columns(df, _REQUIRED_COLUMNS)

    base = df.with_row_index("__row").sort(["trading_date", "ts_recv", "__row"])
    
    # 1. Base Setup Indicators
    # Use a floor for daily_sigma on NQ to prevent micro-targets (e.g. 20.0 pts)
    clamped_sigma = pl.col("daily_sigma").clip(20.0, None)
    
    setup_sigma_signed = (
        pl.when(
            pl.all_horizontal(
                pl.col("daily_vwap").is_not_null(),
                pl.col("daily_sigma").is_not_null(),
                pl.col("daily_sigma") != 0,
            )
        )
        .then((pl.col("structural_reference_price") - pl.col("daily_vwap")) / clamped_sigma)
        .otherwise(None)
        .alias("setup_sigma_signed")
    )

    # 2. Rejection Primitives
    # Displacement logic (causal per trading_date)
    # We need session high/low for rejection check
    rejection_base = base.with_columns(
        pl.col("ask_px_00").cum_max().over("trading_date").alias("session_high"),
        pl.col("bid_px_00").cum_min().over("trading_date").alias("session_low"),
    )
    
    rejection_base = rejection_base.with_columns(
        (pl.col("session_high") != pl.col("session_high").shift(1).over("trading_date")).fill_null(True).cast(pl.Int32).cum_sum().over("trading_date").alias("high_update_count"),
        (pl.col("session_low") != pl.col("session_low").shift(1).over("trading_date")).fill_null(True).cast(pl.Int32).cum_sum().over("trading_date").alias("low_update_count"),
    ).with_columns(
        (pl.int_range(0, pl.len()).over("trading_date", "high_update_count") - pl.int_range(0, pl.len()).over("trading_date", "high_update_count").first()).alias("seconds_since_high_extreme"),
        (pl.int_range(0, pl.len()).over("trading_date", "low_update_count") - pl.int_range(0, pl.len()).over("trading_date", "low_update_count").first()).alias("seconds_since_low_extreme"),
    )

    enriched = rejection_base.with_columns(
        pl.col("ts_recv_et").dt.time().is_between(window_start, window_end, closed="both").alias("time_window_passes"),
        setup_sigma_signed,
    ).with_columns(
        pl.when(pl.col("setup_sigma_signed").is_null())
        .then(False)
        .otherwise(pl.col("setup_sigma_signed").abs().is_between(min_sigma, max_sigma, closed="both"))
        .alias("vwap_extension_passes"),
        (pl.col("structural_levels_within_threshold") >= 1).alias("structural_confluence_passes"),
        pl.when(pl.col("setup_sigma_signed") > 0)
        .then(pl.lit("short"))
        .when(pl.col("setup_sigma_signed") < 0)
        .then(pl.lit("long"))
        .otherwise(None)
        .alias("setup_direction"),
    ).with_columns(
        pl.all_horizontal(
            "time_window_passes",
            "vwap_extension_passes",
            "structural_confluence_passes",
        ).alias("setup_candidate_passes")
    )
    
    # 3. Confluence Scoring
    # Sigma Term (0-40)
    sigma_score = (
        (pl.col("setup_sigma_signed").abs() - 1.7) / (3.0 - 1.7) * 40
    ).clip(0, 40).fill_null(0).alias("sigma_term")
    
    # Structure Term (0-40)
    # Phase 9: 20 pts per unique type (we only have VA types currently, wait)
    # Actually PHASE 3 added structural_levels_within_threshold. 
    # PHASE 7 expanded to Overnight VA, HTF Balance.
    # Let's assume structural_levels_within_threshold counts unique type hits from upstream.
    structure_score = (pl.col("structural_levels_within_threshold") * 20).clip(0, 40).fill_null(0).alias("structure_term")
    
    # Alignment Term (0-20)
    # 10 pts per alignment with Multi-TF VWAP
    weekly_alignment = (
        pl.when(pl.col("setup_direction") == "short")
        .then(pl.col("structural_reference_price") > pl.col("weekly_vwap"))
        .when(pl.col("setup_direction") == "long")
        .then(pl.col("structural_reference_price") < pl.col("weekly_vwap"))
        .otherwise(False)
        .fill_null(False)
    )
    monthly_alignment = (
        pl.when(pl.col("setup_direction") == "short")
        .then(pl.col("structural_reference_price") > pl.col("monthly_vwap"))
        .when(pl.col("setup_direction") == "long")
        .then(pl.col("structural_reference_price") < pl.col("monthly_vwap"))
        .otherwise(False)
        .fill_null(False)
    )
    alignment_score = (
        (weekly_alignment.cast(pl.Int32) * 10) + (monthly_alignment.cast(pl.Int32) * 10)
    ).alias("alignment_term")
    
    enriched = enriched.with_columns(
        (sigma_score + structure_score + alignment_score).alias("confluence_score")
    )

    # 4. Rejection Confirmation & Event Emission
    # Rejection rule: 60s since high extreme + 8 ticks displacement (2 points)
    # Displacement: session_high - current_price for shorts
    # Rejection rule: 60s since high extreme + 5 ticks displacement (5 points)
    enriched = enriched.with_columns(
        pl.when(pl.col("setup_direction") == "short")
        .then(pl.col("seconds_since_high_extreme"))
        .when(pl.col("setup_direction") == "long")
        .then(pl.col("seconds_since_low_extreme"))
        .otherwise(0)
        .alias("seconds_since_extreme"),
        pl.when(pl.col("setup_direction") == "short")
        .then(pl.col("session_high") - pl.col("bid_px_00"))
        .when(pl.col("setup_direction") == "long")
        .then(pl.col("ask_px_00") - pl.col("session_low"))
        .otherwise(0.0)
        .alias("rejection_displacement")
    ).with_columns(
        (
            (pl.col("seconds_since_extreme") >= 60) &
            (pl.col("rejection_displacement") >= 5.0)
        ).alias("rejection_confirmed")
    )
    
    # Event Emission: Only if rejection confirmed while candidate passes
    # Let's use cum_sum of candidate_passes over trading_date to identify setup windows
    enriched = enriched.with_columns(
        (pl.col("setup_candidate_passes") & ~pl.col("setup_candidate_passes").shift(1).over("trading_date").fill_null(False))
        .cast(pl.Int32)
        .cum_sum()
        .over("trading_date")
        .alias("setup_window_id")
    )
    
    # Only allow rejection within a window where candidate is true
    enriched = enriched.with_columns(
        (
            pl.col("setup_candidate_passes").any().over("trading_date", "setup_window_id") &
            pl.col("rejection_confirmed")
        ).alias("setup_event_passes")
    ).with_columns(
        (
            pl.col("setup_event_passes") &
            ~pl.col("setup_event_passes").shift(1).over("trading_date").fill_null(False) &
            (pl.col("setup_window_id") > 0)
        ).alias("setup_event_raw")
    ).with_columns(
        # Limit to ONE event per day (first true rejection)
        (
            pl.col("setup_event_raw") & 
            (pl.col("setup_event_raw").cast(pl.Int32).cum_sum().over("trading_date") == 1)
        ).alias("setup_event_emitted")
    )

    return enriched.sort("__row").drop(["__row", "session_high", "session_low", "high_update_count", "low_update_count", "seconds_since_high_extreme", "seconds_since_low_extreme", "setup_window_id", "setup_event_passes", "setup_event_raw"])


def extract_setup_events(enriched_df: pl.DataFrame) -> pl.DataFrame:
    """Project the compact event log from an enriched setup frame."""

    _require_columns(
        enriched_df,
        {
            "trading_date",
            "ts_recv",
            "ts_recv_et",
            "structural_reference_price",
            "daily_vwap",
            "daily_sigma",
            "setup_sigma_signed",
            "setup_direction",
            "nearest_structural_level",
            "nearest_structural_distance",
            "structural_levels_within_threshold",
            "setup_event_emitted",
            "confluence_score",
            "seconds_since_extreme",
            "rejection_displacement",
        },
    )
    
    columns = [
        "trading_date",
        "ts_recv",
        "ts_recv_et",
        "structural_reference_price",
        "daily_vwap",
        "daily_sigma",
        "setup_sigma_signed",
        "setup_direction",
        "nearest_structural_level",
        "nearest_structural_distance",
        "structural_levels_within_threshold",
        "confluence_score",
    ]
    for optional_column in ("bid_px_00", "ask_px_00", "regime_label", "regime_reason"):
        if optional_column in enriched_df.columns:
            columns.append(optional_column)

    return (
        enriched_df.filter(pl.col("setup_event_emitted"))
        .sort(["trading_date", "ts_recv"])
        .select(columns)
    )


def write_setup_detection_artifacts(
    df: pl.DataFrame,
    output_dir: Path,
    window_start: time = time(9, 30),
    window_end: time = time(11, 30),
    min_sigma: float = 1.7,
    max_sigma: float = 3.0,
) -> tuple[Path, Path]:
    """Persist the row-level setup frame and compact setup log."""

    output_dir.mkdir(parents=True, exist_ok=True)
    enriched = attach_setup_detection_features(
        df,
        window_start=window_start,
        window_end=window_end,
        min_sigma=min_sigma,
        max_sigma=max_sigma,
    )
    setup_log = extract_setup_events(enriched).with_columns(
        pl.lit(None, dtype=pl.Utf8).alias("regime_label"), # To be filled by simulation if needed or kept as placeholder
        pl.lit(None, dtype=pl.Utf8).alias("regime_reason"),
    )

    enriched_path = output_dir / _ENRICHED_ARTIFACT_NAME
    setup_log_path = output_dir / _SETUP_LOG_ARTIFACT_NAME
    enriched.write_parquet(enriched_path)
    setup_log.write_parquet(setup_log_path)
    return enriched_path, setup_log_path


def write_setup_validation_export(enriched_df: pl.DataFrame, output_dir: Path, validation_dates: list[str]) -> None:
    """Write deterministic setup-validation exports for selected sessions."""

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
    comparison.write_csv(validation_dir / _VALIDATION_EXPORT_NAME)

    manifest = {
        "validation_dates": normalized_dates,
        "enriched_artifact": _ENRICHED_ARTIFACT_NAME,
        "setup_log_artifact": _SETUP_LOG_ARTIFACT_NAME,
        "comparison_export": f"validation/{_VALIDATION_EXPORT_NAME}",
        "row_count": comparison.height,
    }
    (validation_dir / _VALIDATION_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
