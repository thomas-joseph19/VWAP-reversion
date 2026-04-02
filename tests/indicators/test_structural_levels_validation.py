from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

from vwap_revert.cli import main
from vwap_revert.data_pipeline.cache import write_canonical_cache
from vwap_revert.indicators.structural_levels import (
    attach_prior_day_structural_levels,
    write_structural_levels_artifacts,
    write_structural_validation_export,
)


COMPARISON_COLUMNS = [
    "trading_date",
    "ts_recv_et",
    "structural_reference_price",
    "source_trading_date",
    "prior_rth_vah",
    "prior_rth_val",
    "prior_rth_poc",
    "distance_to_prior_rth_vah",
    "distance_to_prior_rth_val",
    "distance_to_prior_rth_poc",
    "nearest_structural_level",
    "nearest_structural_distance",
    "structural_levels_within_threshold",
    "levels_available",
    "quality_status",
]


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _fixture_frame() -> pl.DataFrame:
    rows: list[dict[str, object]] = []

    for offset, trading_day in enumerate([date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)], start=0):
        base_price = 100.0 + (offset * 10.0)
        rows.extend(
            [
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 14, 30, 0),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 9, 30, 0),
                    "is_rth": True,
                    "side": "B",
                    "price": base_price,
                    "size": 5.0,
                    "bid_px_00": base_price - 0.25,
                    "ask_px_00": base_price + 0.25,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 14, 30, 1),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 9, 30, 1),
                    "is_rth": True,
                    "side": "A",
                    "price": base_price + 1.0,
                    "size": 3.0,
                    "bid_px_00": base_price + 0.75,
                    "ask_px_00": base_price + 1.25,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 14, 30, 2),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 9, 30, 2),
                    "is_rth": True,
                    "side": "N",
                    "price": base_price + 0.5,
                    "size": 0.0,
                    "bid_px_00": base_price + 0.25,
                    "ask_px_00": base_price + 0.75,
                },
            ]
        )

    return pl.DataFrame(rows, strict=False)


def _make_temp_dir() -> Path:
    root = Path(".codex_tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    return path


def test_structural_validation_export_contains_expected_columns() -> None:
    tmp_path = _make_temp_dir()
    try:
        session_path, enriched_path = write_structural_levels_artifacts(_fixture_frame(), tmp_path)
        enriched = attach_prior_day_structural_levels(_fixture_frame())
        write_structural_validation_export(enriched, tmp_path, ["2024-01-03", "2024-01-04"])

        comparison_path = tmp_path / "validation" / "structural_validation_export.csv"
        manifest_path = tmp_path / "validation" / "validation_sessions.json"

        assert session_path.exists()
        assert enriched_path.exists()
        assert comparison_path.exists()
        assert manifest_path.exists()

        comparison = pl.read_csv(comparison_path, try_parse_dates=True)
        assert comparison.columns == COMPARISON_COLUMNS
        assert comparison["trading_date"].dt.strftime("%Y-%m-%d").unique().sort().to_list() == ["2024-01-03", "2024-01-04"]

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["validation_dates"] == ["2024-01-03", "2024-01-04"]
        assert manifest["session_artifact"] == "phase3_structural_levels.parquet"
        assert manifest["enriched_artifact"] == "phase3_structural_enriched.parquet"
        assert manifest["comparison_export"] == "validation/structural_validation_export.csv"
        assert manifest["row_count"] == comparison.height
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_cli_writes_phase3_structural_artifacts() -> None:
    tmp_path = _make_temp_dir()
    cache_root = tmp_path / "canonical_cache"
    output_root = tmp_path / "phase3_output"
    try:
        write_canonical_cache(_fixture_frame(), cache_root)

        exit_code = main(
            [
                "build-phase3-structural-levels",
                "--cache-root",
                str(cache_root),
                "--output-root",
                str(output_root),
                "--validation-date",
                "2024-01-03",
                "--validation-date",
                "2024-01-04",
            ]
        )

        assert exit_code == 0
        assert (output_root / "phase3_structural_levels.parquet").exists()
        assert (output_root / "phase3_structural_enriched.parquet").exists()
        assert (output_root / "validation" / "structural_validation_export.csv").exists()
        assert (output_root / "validation" / "validation_sessions.json").exists()

        manifest = json.loads((output_root / "validation" / "validation_sessions.json").read_text(encoding="utf-8"))
        assert manifest["validation_dates"] == ["2024-01-03", "2024-01-04"]
        assert sorted(manifest) == [
            "comparison_export",
            "enriched_artifact",
            "row_count",
            "session_artifact",
            "validation_dates",
        ]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
