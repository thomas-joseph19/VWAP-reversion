"""Daily VWAP indicator helpers."""

from __future__ import annotations

import json
from pathlib import Path

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
_ENRICHED_ARTIFACT_NAME = "phase2_daily_vwap.parquet"
_VALIDATION_EXPORT_NAME = "vwap_validation_export.csv"
_VALIDATION_MANIFEST_NAME = "validation_sessions.json"
_VALIDATION_COLUMNS = [
    "trading_date",
    "ts_recv_et",
    "price",
    "size",
    *_BAND_COLUMNS,
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


def write_enriched_vwap_artifact(enriched_df: pl.DataFrame, output_dir: Path) -> Path:
    """Persist the row-aligned phase-2 dataset for downstream reuse."""

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / _ENRICHED_ARTIFACT_NAME
    enriched_df.write_parquet(artifact_path)
    return artifact_path


def write_vwap_validation_export(enriched_df: pl.DataFrame, output_dir: Path, validation_dates: list[str]) -> None:
    """Write deterministic validation artifacts for manual chart comparison."""

    normalized_dates = sorted(dict.fromkeys(validation_dates))
    if not normalized_dates:
        raise ValueError("validation_dates must include at least one YYYY-MM-DD value")

    _require_columns(enriched_df, {"ts_recv_et", "trading_date", "price", "size", *_BAND_COLUMNS})

    output_dir.mkdir(parents=True, exist_ok=True)
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    write_enriched_vwap_artifact(enriched_df, output_dir)

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
        "comparison_export": f"validation/{_VALIDATION_EXPORT_NAME}",
        "row_count": comparison.height,
    }
    (validation_dir / _VALIDATION_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
