from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

from vwap_revert.cli import main
from vwap_revert.data_pipeline.cache import write_canonical_cache
from vwap_revert.indicators.vwap import attach_daily_vwap_bands, write_vwap_validation_export


COMPARISON_COLUMNS = [
    "trading_date",
    "ts_recv_et",
    "price",
    "size",
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


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _fixture_frame() -> pl.DataFrame:
    rows: list[dict[str, object]] = []

    for day in range(2, 7):
        trading_day = date(2024, 1, day)
        rows.extend(
            [
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(2024, 1, day, 14, 30, 0),
                    "ts_recv_et": _ts(2024, 1, day, 9, 30, 0),
                    "is_rth": True,
                    "side": "B",
                    "price": 100.0 + day,
                    "size": 1.0,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(2024, 1, day, 14, 30, 1),
                    "ts_recv_et": _ts(2024, 1, day, 9, 30, 1),
                    "is_rth": True,
                    "side": "N",
                    "price": 100.5 + day,
                    "size": 2.0,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(2024, 1, day, 14, 30, 2),
                    "ts_recv_et": _ts(2024, 1, day, 9, 30, 2),
                    "is_rth": True,
                    "side": "A",
                    "price": 101.0 + day,
                    "size": 3.0,
                },
            ]
        )

    return pl.DataFrame(rows)


def _make_temp_dir() -> Path:
    root = Path(".codex_tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    return path


def test_validation_export_contains_comparison_columns() -> None:
    tmp_path = _make_temp_dir()
    enriched = attach_daily_vwap_bands(_fixture_frame())
    validation_dates = [f"2024-01-0{day}" for day in range(2, 7)]

    try:
        write_vwap_validation_export(enriched, tmp_path, validation_dates)

        enriched_path = tmp_path / "phase2_daily_vwap.parquet"
        comparison_path = tmp_path / "validation" / "vwap_validation_export.csv"
        manifest_path = tmp_path / "validation" / "validation_sessions.json"

        assert enriched_path.exists()
        assert comparison_path.exists()
        assert manifest_path.exists()

        comparison = pl.read_csv(comparison_path, try_parse_dates=True)
        assert comparison.columns == COMPARISON_COLUMNS
        assert comparison["trading_date"].dt.strftime("%Y-%m-%d").unique().sort().to_list() == validation_dates

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["validation_dates"] == validation_dates
        assert manifest["comparison_export"] == "validation/vwap_validation_export.csv"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_cli_writes_indicator_and_validation_artifacts() -> None:
    tmp_path = _make_temp_dir()
    cache_root = tmp_path / "canonical_cache"
    output_root = tmp_path / "phase2_output"
    try:
        write_canonical_cache(_fixture_frame(), cache_root)

        exit_code = main(
            [
                "build-phase2-vwap",
                "--cache-root",
                str(cache_root),
                "--output-root",
                str(output_root),
                "--validation-date",
                "2024-01-02",
                "--validation-date",
                "2024-01-03",
                "--validation-date",
                "2024-01-04",
                "--validation-date",
                "2024-01-05",
                "--validation-date",
                "2024-01-06",
            ]
        )

        assert exit_code == 0
        assert (output_root / "phase2_daily_vwap.parquet").exists()
        assert (output_root / "validation" / "vwap_validation_export.csv").exists()
        assert (output_root / "validation" / "validation_sessions.json").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
