from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

from vwap_revert.cli import main
from vwap_revert.data_pipeline.cache import write_canonical_cache
from vwap_revert.indicators.setup_detection import (
    attach_setup_detection_features,
    write_setup_detection_artifacts,
    write_setup_validation_export,
)


COMPARISON_COLUMNS = [
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


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _detector_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                date(2024, 1, 3),
                date(2024, 1, 3),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 4),
            ],
            "ts_recv": [
                _ts(2024, 1, 3, 14, 30, 0),
                _ts(2024, 1, 3, 14, 30, 1),
                _ts(2024, 1, 3, 14, 30, 2),
                _ts(2024, 1, 4, 14, 30, 0),
                _ts(2024, 1, 4, 14, 30, 1),
            ],
            "ts_recv_et": [
                _ts(2024, 1, 3, 9, 30, 0),
                _ts(2024, 1, 3, 9, 30, 1),
                _ts(2024, 1, 3, 9, 30, 2),
                _ts(2024, 1, 4, 9, 30, 0),
                _ts(2024, 1, 4, 9, 30, 1),
            ],
            "daily_vwap": [115.0, 115.0, 115.0, 116.0, 116.0],
            "daily_sigma": [5.0, 5.0, 5.0, 4.0, 4.0],
            "structural_reference_price": [105.0, 105.0, 130.0, 124.0, 124.0],
            "structural_levels_within_threshold": [1, 1, 1, 1, 1],
            "nearest_structural_level": [
                "prior_rth_vah",
                "prior_rth_vah",
                "prior_rth_poc",
                "prior_rth_vah",
                "prior_rth_vah",
            ],
            "nearest_structural_distance": [3.0, 3.0, 0.5, 1.0, 1.0],
            "bid_px_00": [104.75, 104.75, 129.75, 123.75, 123.75],
            "ask_px_00": [105.25, 105.25, 130.25, 124.25, 124.25],
        },
        strict=False,
    )


def _canonical_fixture() -> pl.DataFrame:
    rows: list[dict[str, object]] = []

    day2 = date(2024, 1, 2)
    rows.extend(
        [
            {
                "trading_date": day2,
                "ts_recv": _ts(2024, 1, 2, 14, 30, 0),
                "ts_recv_et": _ts(2024, 1, 2, 9, 30, 0),
                "is_rth": True,
                "side": "B",
                "price": 100.0,
                "size": 5.0,
                "bid_px_00": 99.75,
                "ask_px_00": 100.25,
            },
            {
                "trading_date": day2,
                "ts_recv": _ts(2024, 1, 2, 14, 30, 1),
                "ts_recv_et": _ts(2024, 1, 2, 9, 30, 1),
                "is_rth": True,
                "side": "A",
                "price": 102.0,
                "size": 5.0,
                "bid_px_00": 101.75,
                "ask_px_00": 102.25,
            },
        ]
    )

    day3 = date(2024, 1, 3)
    rows.extend(
        [
            {
                "trading_date": day3,
                "ts_recv": _ts(2024, 1, 3, 14, 30, 0),
                "ts_recv_et": _ts(2024, 1, 3, 9, 30, 0),
                "is_rth": True,
                "side": "B",
                "price": 110.0,
                "size": 5.0,
                "bid_px_00": 109.75,
                "ask_px_00": 110.25,
            },
            {
                "trading_date": day3,
                "ts_recv": _ts(2024, 1, 3, 14, 30, 1),
                "ts_recv_et": _ts(2024, 1, 3, 9, 30, 1),
                "is_rth": True,
                "side": "A",
                "price": 120.0,
                "size": 5.0,
                "bid_px_00": 119.75,
                "ask_px_00": 120.25,
            },
            {
                "trading_date": day3,
                "ts_recv": _ts(2024, 1, 3, 14, 30, 2),
                "ts_recv_et": _ts(2024, 1, 3, 9, 30, 2),
                "is_rth": True,
                "side": "N",
                "price": 105.0,
                "size": 0.0,
                "bid_px_00": 104.75,
                "ask_px_00": 105.25,
            },
        ]
    )

    day4 = date(2024, 1, 4)
    rows.extend(
        [
            {
                "trading_date": day4,
                "ts_recv": _ts(2024, 1, 4, 14, 30, 0),
                "ts_recv_et": _ts(2024, 1, 4, 9, 30, 0),
                "is_rth": True,
                "side": "B",
                "price": 112.0,
                "size": 5.0,
                "bid_px_00": 111.75,
                "ask_px_00": 112.25,
            },
            {
                "trading_date": day4,
                "ts_recv": _ts(2024, 1, 4, 14, 30, 1),
                "ts_recv_et": _ts(2024, 1, 4, 9, 30, 1),
                "is_rth": True,
                "side": "A",
                "price": 120.0,
                "size": 5.0,
                "bid_px_00": 119.75,
                "ask_px_00": 120.25,
            },
            {
                "trading_date": day4,
                "ts_recv": _ts(2024, 1, 4, 14, 30, 2),
                "ts_recv_et": _ts(2024, 1, 4, 9, 30, 2),
                "is_rth": True,
                "side": "N",
                "price": 124.0,
                "size": 0.0,
                "bid_px_00": 123.75,
                "ask_px_00": 124.25,
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


def test_setup_validation_export_contains_expected_columns() -> None:
    tmp_path = _make_temp_dir()
    try:
        enriched = attach_setup_detection_features(_detector_fixture())
        enriched_path, setup_log_path = write_setup_detection_artifacts(_detector_fixture(), tmp_path)
        write_setup_validation_export(enriched, tmp_path, ["2024-01-03", "2024-01-04"])

        comparison_path = tmp_path / "validation" / "setup_validation_export.csv"
        manifest_path = tmp_path / "validation" / "validation_sessions.json"

        assert enriched_path.exists()
        assert setup_log_path.exists()
        assert comparison_path.exists()
        assert manifest_path.exists()

        comparison = pl.read_csv(comparison_path, try_parse_dates=True)
        assert comparison.columns == COMPARISON_COLUMNS
        assert comparison["trading_date"].dt.strftime("%Y-%m-%d").unique().sort().to_list() == ["2024-01-03", "2024-01-04"]

        setup_log = pl.read_parquet(setup_log_path)
        assert "regime_label" in setup_log.columns
        assert "regime_reason" in setup_log.columns
        assert setup_log["regime_label"].to_list() == [None, None]
        assert setup_log["regime_reason"].to_list() == [None, None]

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["validation_dates"] == ["2024-01-03", "2024-01-04"]
        assert manifest["enriched_artifact"] == "phase4_setup_enriched.parquet"
        assert manifest["setup_log_artifact"] == "phase4_setup_log.parquet"
        assert manifest["comparison_export"] == "validation/setup_validation_export.csv"
        assert manifest["row_count"] == comparison.height
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_cli_writes_phase4_setup_artifacts() -> None:
    tmp_path = _make_temp_dir()
    cache_root = tmp_path / "canonical_cache"
    output_root = tmp_path / "phase4_output"
    try:
        write_canonical_cache(_canonical_fixture(), cache_root)

        exit_code = main(
            [
                "build-phase4-setup-detection",
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
        assert (output_root / "phase4_setup_enriched.parquet").exists()
        assert (output_root / "phase4_setup_log.parquet").exists()
        assert (output_root / "validation" / "setup_validation_export.csv").exists()
        assert (output_root / "validation" / "validation_sessions.json").exists()

        setup_log = pl.read_parquet(output_root / "phase4_setup_log.parquet")
        assert setup_log["setup_direction"].to_list() == ["long", "short"]
        assert "regime_label" in setup_log.columns
        assert "regime_reason" in setup_log.columns

        manifest = json.loads((output_root / "validation" / "validation_sessions.json").read_text(encoding="utf-8"))
        assert sorted(manifest) == [
            "comparison_export",
            "enriched_artifact",
            "row_count",
            "setup_log_artifact",
            "validation_dates",
        ]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
