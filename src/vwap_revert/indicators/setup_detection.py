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
    setup_sigma_signed = (
        pl.when(
            pl.all_horizontal(
                pl.col("daily_vwap").is_not_null(),
                pl.col("daily_sigma").is_not_null(),
                pl.col("daily_sigma") != 0,
            )
        )
        .then((pl.col("structural_reference_price") - pl.col("daily_vwap")) / pl.col("daily_sigma"))
        .otherwise(None)
        .alias("setup_sigma_signed")
    )

    enriched = base.with_columns(
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
    ).with_columns(
        (
            pl.col("setup_candidate_passes")
            & ~pl.col("setup_candidate_passes").shift(1).over("trading_date").fill_null(False)
        ).alias("setup_event_emitted")
    )

    return enriched.sort("__row").drop("__row")


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
    ]
    for optional_column in ("bid_px_00", "ask_px_00"):
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
        pl.lit(None, dtype=pl.Utf8).alias("regime_label"),
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
