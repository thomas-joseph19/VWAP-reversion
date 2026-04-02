from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from vwap_revert.cli import build_phase1_cache
from vwap_revert.data_pipeline.cache import scan_canonical_cache, write_canonical_cache


def test_partitioned_cache_layout(tmp_path: Path) -> None:
    frame = pl.DataFrame(
        {
            "trading_date": ["2024-01-02", "2024-01-03"],
            "ts_recv_et": [
                "2024-01-02T09:30:00-05:00",
                "2024-01-03T09:30:00-05:00",
            ],
            "session_name": ["rth", "rth"],
        }
    ).with_columns(
        pl.col("trading_date").str.strptime(pl.Date, strict=True),
        pl.col("ts_recv_et").str.strptime(pl.Datetime("ns", "America/New_York"), strict=True),
    )

    output_dir = tmp_path / "cache"
    write_canonical_cache(frame, output_dir)

    assert sorted(path.name for path in output_dir.iterdir()) == [
        "trading_date=2024-01-02",
        "trading_date=2024-01-03",
    ]
    assert scan_canonical_cache(output_dir).collect().height == 2


def test_cache_benchmark_artifact_records_reload_target(tmp_path: Path) -> None:
    csv_root = tmp_path / "csv"
    csv_root.mkdir()
    csv_root.joinpath("GLBX-20240102.csv").write_text(
        (
            "ts_recv,ts_event,rtype,publisher_id,instrument_id,side,price,size,flags,sequence,"
            "bid_px_00,ask_px_00,bid_sz_00,ask_sz_00,bid_ct_00,ask_ct_00,symbol\n"
            "2024-01-02T14:30:00.000000000Z,2024-01-02T14:30:00.000000000Z,1,1,10,A,17000.25,2,0,1,17000.00,17000.50,10,11,1,1,NQH4\n"
            "2024-01-02T15:30:00.000000000Z,2024-01-02T15:30:00.000000000Z,1,1,10,B,17001.25,3,0,2,17001.00,17001.50,10,11,1,1,NQH4\n"
        ),
        encoding="utf-8",
    )

    output_root = tmp_path / "output"
    benchmark = build_phase1_cache(csv_root, output_root, None)
    artifact = json.loads((output_root / "cache_benchmark.json").read_text(encoding="utf-8"))

    assert (output_root / "contract_roll_map.parquet").exists()
    assert (output_root / "schema_summary.json").exists()
    assert (output_root / "data_quality_report.json").exists()
    assert artifact["reload_under_30_seconds"] is True
    assert set(benchmark) == {
        "first_build_seconds",
        "cache_reload_seconds",
        "reload_under_30_seconds",
    }
