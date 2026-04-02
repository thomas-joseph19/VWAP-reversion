from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

from vwap_revert.cli import main


VALIDATION_COLUMNS = [
    "trading_date",
    "entry_ts",
    "exit_ts",
    "direction",
    "entry_price",
    "exit_price",
    "exit_reason",
    "gross_points",
    "net_dollars",
    "mae_points",
    "duration_seconds",
    "setup_sigma_signed",
    "nearest_structural_level",
    "nearest_structural_distance",
    "regime_label",
    "regime_reason",
]


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _make_temp_dir() -> Path:
    root = Path(".codex_tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    return path


def _phase4_setup_log_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [date(2024, 1, 3), date(2024, 1, 3)],
            "ts_recv": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 30, 1)],
            "ts_recv_et": [_ts(2024, 1, 3, 9, 30, 0), _ts(2024, 1, 3, 9, 30, 1)],
            "setup_direction": ["long", "short"],
            "daily_vwap": [101.0, 101.0],
            "daily_sigma": [5.0, 5.0],
            "setup_sigma_signed": [-2.1, 2.3],
            "nearest_structural_level": ["prior_rth_val", "prior_rth_vah"],
            "nearest_structural_distance": [1.5, 1.0],
            "structural_levels_within_threshold": [1, 1],
            "regime_label": ["balanced", "balanced"],
            "regime_reason": ["fixture", "fixture"],
            "bid_px_00": [100.0, 100.5],
            "ask_px_00": [100.25, 100.75],
        },
        strict=False,
    )


def _phase4_enriched_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [date(2024, 1, 3), date(2024, 1, 3), date(2024, 1, 3)],
            "ts_recv": [
                _ts(2024, 1, 3, 14, 30, 0),
                _ts(2024, 1, 3, 14, 30, 1),
                _ts(2024, 1, 3, 14, 30, 2),
            ],
            "ts_recv_et": [
                _ts(2024, 1, 3, 9, 30, 0),
                _ts(2024, 1, 3, 9, 30, 1),
                _ts(2024, 1, 3, 9, 30, 2),
            ],
            "daily_vwap": [101.0, 101.0, 101.0],
            "daily_sigma": [5.0, 5.0, 5.0],
            "setup_sigma_signed": [-2.1, -2.1, -2.1],
            "nearest_structural_level": ["prior_rth_val", "prior_rth_val", "prior_rth_val"],
            "nearest_structural_distance": [1.5, 1.5, 1.5],
            "regime_label": ["balanced", "balanced", "balanced"],
            "regime_reason": ["fixture", "fixture", "fixture"],
            "bid_px_00": [100.0, 100.5, 101.0],
            "ask_px_00": [100.25, 100.75, 101.25],
        },
        strict=False,
    )


def test_cli_writes_phase5_trade_artifacts() -> None:
    tmp_path = _make_temp_dir()
    phase4_root = tmp_path / "phase4_output"
    output_root = tmp_path / "phase5_output"
    try:
        phase4_root.mkdir(parents=True, exist_ok=True)
        _phase4_setup_log_fixture().write_parquet(phase4_root / "phase4_setup_log.parquet")
        _phase4_enriched_fixture().write_parquet(phase4_root / "phase4_setup_enriched.parquet")

        exit_code = main(
            [
                "build-phase5-trade-simulation",
                "--phase4-root",
                str(phase4_root),
                "--output-root",
                str(output_root),
                "--validation-date",
                "2024-01-03",
            ]
        )

        assert exit_code == 0
        assert (output_root / "phase5_trade_log.parquet").exists()
        assert (output_root / "phase5_skipped_setups.parquet").exists()
        assert (output_root / "validation" / "trade_simulation_validation_export.csv").exists()
        assert (output_root / "validation" / "validation_sessions.json").exists()

        trade_log = pl.read_parquet(output_root / "phase5_trade_log.parquet")
        skipped_setups = pl.read_parquet(output_root / "phase5_skipped_setups.parquet")
        comparison = pl.read_csv(
            output_root / "validation" / "trade_simulation_validation_export.csv",
            try_parse_dates=True,
        )
        manifest = json.loads((output_root / "validation" / "validation_sessions.json").read_text(encoding="utf-8"))

        assert trade_log.height == 1
        assert skipped_setups.height == 1
        assert comparison.columns == VALIDATION_COLUMNS
        assert sorted(manifest) == [
            "comparison_export",
            "phase4_enriched_artifact",
            "phase4_setup_log_artifact",
            "row_count",
            "skipped_setups_artifact",
            "stop_loss_baseline_note",
            "trade_log_artifact",
            "validation_dates",
        ]
        assert manifest["phase4_setup_log_artifact"] == "phase4_setup_log.parquet"
        assert manifest["phase4_enriched_artifact"] == "phase4_setup_enriched.parquet"
        assert manifest["trade_log_artifact"] == "phase5_trade_log.parquet"
        assert manifest["skipped_setups_artifact"] == "phase5_skipped_setups.parquet"
        assert manifest["comparison_export"] == "validation/trade_simulation_validation_export.csv"
        assert manifest["validation_dates"] == ["2024-01-03"]
        assert manifest["row_count"] == comparison.height
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
