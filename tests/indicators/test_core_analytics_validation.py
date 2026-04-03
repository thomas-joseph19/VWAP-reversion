from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

from vwap_revert.cli import main


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _make_temp_dir() -> Path:
    root = Path(".codex_tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    return path


def _phase5_trade_log_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [date(2024, 1, 3), date(2024, 1, 3), date(2024, 1, 4)],
            "direction": ["long", "short", "long"],
            "signal_ts": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 45, 0), _ts(2024, 1, 4, 14, 30, 0)],
            "entry_ts": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 45, 0), _ts(2024, 1, 4, 14, 30, 0)],
            "entry_price": [100.25, 101.75, 102.0],
            "exit_ts": [_ts(2024, 1, 3, 14, 35, 0), _ts(2024, 1, 3, 14, 50, 0), _ts(2024, 1, 4, 14, 35, 0)],
            "exit_price": [101.25, 102.25, 102.5],
            "exit_reason": ["target_vwap", "stop_loss", "target_vwap"],
            "target_price": [101.0, 101.0, 102.25],
            "gross_points": [1.0, -0.5, 0.5],
            "net_dollars": [15.0, -25.0, 35.0],
            "mae_points": [0.25, 0.5, 0.25],
            "duration_seconds": [300.0, 300.0, 300.0],
            "setup_sigma_signed": [-2.1, 2.3, -1.8],
            "nearest_structural_level": ["prior_rth_val", "prior_rth_vah", "prior_eth_mid"],
            "nearest_structural_distance": [1.5, 1.0, 0.75],
            "regime_label": ["balanced", "trend", "balanced"],
            "regime_reason": ["fixture", "fixture", "fixture"],
        },
        strict=False,
    )


def test_cli_writes_phase6_analytics_artifacts() -> None:
    tmp_path = _make_temp_dir()
    phase5_root = tmp_path / "phase5_output"
    output_root = tmp_path / "phase6_output"
    try:
        phase5_root.mkdir(parents=True, exist_ok=True)
        _phase5_trade_log_fixture().write_parquet(phase5_root / "phase5_trade_log.parquet")

        exit_code = main(
            [
                "build-phase6-core-analytics",
                "--phase5-root",
                str(phase5_root),
                "--output-root",
                str(output_root),
                "--validation-date",
                "2024-01-03",
                "--validation-date",
                "2024-01-04",
            ]
        )

        assert exit_code == 0
        assert (output_root / "phase6_trade_log.csv").exists()
        assert (output_root / "phase6_metrics.json").exists()
        assert (output_root / "validation" / "core_analytics_validation_export.csv").exists()
        assert (output_root / "validation" / "validation_sessions.json").exists()

        trade_log = pl.read_csv(output_root / "phase6_trade_log.csv", try_parse_dates=True)
        metrics = json.loads((output_root / "phase6_metrics.json").read_text(encoding="utf-8"))
        validation_export = pl.read_csv(
            output_root / "validation" / "core_analytics_validation_export.csv",
            try_parse_dates=True,
        )
        manifest = json.loads((output_root / "validation" / "validation_sessions.json").read_text(encoding="utf-8"))

        assert trade_log.columns == [
            "trading_date",
            "direction",
            "signal_ts",
            "entry_ts",
            "entry_price",
            "exit_ts",
            "exit_price",
            "exit_reason",
            "target_price",
            "gross_points",
            "net_dollars",
            "mae_points",
            "duration_seconds",
            "setup_sigma_signed",
            "nearest_structural_level",
            "nearest_structural_distance",
            "regime_label",
            "regime_reason",
            "pnl_points",
            "pnl_ticks",
            "sigma_at_entry",
        ]
        for column in [
            "trading_date",
            "entry_ts",
            "exit_ts",
            "entry_price",
            "exit_price",
            "pnl_points",
            "pnl_ticks",
            "net_dollars",
            "duration_seconds",
            "sigma_at_entry",
            "nearest_structural_level",
            "regime_label",
            "regime_reason",
        ]:
            assert column in validation_export.columns

        assert sorted(metrics) == [
            "average_loss_dollars",
            "average_win_dollars",
            "average_win_loss_ratio",
            "losses",
            "max_drawdown_dollars",
            "profit_factor",
            "sharpe_ratio",
            "total_net_dollars",
            "trade_count",
            "win_rate",
            "wins",
        ]
        assert sorted(manifest) == [
            "metrics_json_artifact",
            "phase5_trade_log_artifact",
            "row_count",
            "sharpe_convention",
            "tick_size",
            "trade_log_csv_artifact",
            "validation_dates",
            "validation_export",
        ]
        assert manifest["phase5_trade_log_artifact"] == "phase5_trade_log.parquet"
        assert manifest["trade_log_csv_artifact"] == "phase6_trade_log.csv"
        assert manifest["metrics_json_artifact"] == "phase6_metrics.json"
        assert manifest["validation_export"] == "validation/core_analytics_validation_export.csv"
        assert manifest["validation_dates"] == ["2024-01-03", "2024-01-04"]
        assert manifest["row_count"] == validation_export.height
        assert manifest["tick_size"] == 0.25
        assert (
            manifest["sharpe_convention"]
            == "mean(net_dollars) / sample_std(net_dollars) * sqrt(trade_count); null if trade_count < 2 or std == 0"
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
