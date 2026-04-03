from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

from vwap_revert.cli import main


COMPARISON_COLUMNS = [
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


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _make_temp_dir() -> Path:
    root = Path(".codex_tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    return path


def _phase7_cli_fixture() -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    sessions = [
        (date(2023, 9, 18), "NQU3", 15000.0, 14998.0),
        (date(2023, 9, 19), "NQZ3", 15100.0, 15098.0),
        (date(2023, 9, 20), "NQZ3", 15150.0, 15148.0),
    ]

    for trading_day, front_symbol, rth_base, overnight_base in sessions:
        rows.extend(
            [
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day - 1, 23, 0),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day - 1, 23, 0),
                    "is_overnight": True,
                    "is_rth": False,
                    "side": "A",
                    "price": overnight_base + 0.25,
                    "size": 8.0,
                    "bid_px_00": overnight_base,
                    "ask_px_00": overnight_base + 0.5,
                    "front_symbol": front_symbol,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 0, 15),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 0, 15),
                    "is_overnight": True,
                    "is_rth": False,
                    "side": "B",
                    "price": overnight_base,
                    "size": 12.0,
                    "bid_px_00": overnight_base - 0.25,
                    "ask_px_00": overnight_base + 0.25,
                    "front_symbol": front_symbol,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 30),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 30),
                    "is_overnight": False,
                    "is_rth": True,
                    "side": "A",
                    "price": rth_base,
                    "size": 10.0,
                    "bid_px_00": rth_base - 0.25,
                    "ask_px_00": rth_base + 0.25,
                    "front_symbol": front_symbol,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 31),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 31),
                    "is_overnight": False,
                    "is_rth": True,
                    "side": "B",
                    "price": rth_base + 0.25,
                    "size": 20.0,
                    "bid_px_00": rth_base,
                    "ask_px_00": rth_base + 0.5,
                    "front_symbol": front_symbol,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 32),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 32),
                    "is_overnight": False,
                    "is_rth": True,
                    "side": "A",
                    "price": rth_base + 0.5,
                    "size": 15.0,
                    "bid_px_00": rth_base + 0.25,
                    "ask_px_00": rth_base + 0.75,
                    "front_symbol": front_symbol,
                },
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 33),
                    "ts_recv_et": _ts(trading_day.year, trading_day.month, trading_day.day, 13, 33),
                    "is_overnight": False,
                    "is_rth": True,
                    "side": "N",
                    "price": None,
                    "size": 0.0,
                    "bid_px_00": rth_base + 0.125,
                    "ask_px_00": rth_base + 0.375,
                    "front_symbol": front_symbol,
                },
            ]
        )

    return pl.DataFrame(rows, strict=False)


def _write_partitioned_cache(df: pl.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(
        output_dir,
        use_pyarrow=True,
        compression="zstd",
        pyarrow_options={"partition_cols": ["trading_date"]},
    )


def test_cli_writes_phase7_volume_profile_artifacts() -> None:
    tmp_path = _make_temp_dir()
    cache_root = tmp_path / "canonical_cache"
    output_root = tmp_path / "phase7_output"
    try:
        _write_partitioned_cache(_phase7_cli_fixture(), cache_root)

        exit_code = main(
            [
                "build-phase7-volume-profile",
                "--cache-root",
                str(cache_root),
                "--output-root",
                str(output_root),
                "--validation-date",
                "2023-09-19",
                "--validation-date",
                "2023-09-20",
                "--bucket-size",
                "0.25",
                "--htf-lookback-sessions",
                "180",
            ]
        )

        assert exit_code == 0
        assert (output_root / "phase7_daily_profiles.parquet").exists()
        assert (output_root / "phase7_overnight_profiles.parquet").exists()
        assert (output_root / "phase7_htf_profiles.parquet").exists()
        assert (output_root / "phase7_volume_profile_enriched.parquet").exists()
        assert (output_root / "validation" / "volume_profile_validation_export.csv").exists()
        assert (output_root / "validation" / "validation_sessions.json").exists()

        comparison = pl.read_csv(
            output_root / "validation" / "volume_profile_validation_export.csv",
            try_parse_dates=True,
        )
        assert comparison.columns == COMPARISON_COLUMNS

        mixed_roll_rows = comparison.filter(pl.col("trading_date") == date(2023, 9, 20))
        assert mixed_roll_rows.height > 0
        assert mixed_roll_rows["htf_roll_mixed_window"].all()
        assert mixed_roll_rows["htf_poc"].is_not_null().all()
        assert mixed_roll_rows["htf_vah"].is_not_null().all()
        assert mixed_roll_rows["htf_val"].is_not_null().all()
        assert mixed_roll_rows["phase7_quality_status"].eq("ok").all()

        manifest = json.loads((output_root / "validation" / "validation_sessions.json").read_text(encoding="utf-8"))
        assert sorted(manifest) == [
            "bucket_size",
            "daily_artifact",
            "enriched_artifact",
            "htf_artifact",
            "htf_lookback_sessions",
            "overnight_artifact",
            "row_count",
            "validation_dates",
            "validation_export",
        ]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
