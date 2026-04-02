from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from vwap_revert.data_pipeline.ingest import collect_sample_day, scan_candidate_outrights
from vwap_revert.data_pipeline.manifest import build_manifest


def test_reads_sample_day(write_csv) -> None:
    csv_path = write_csv(
        "GLBX-20240108.csv",
        [
            "2024-01-08T13:30:00.000000000Z,2024-01-08T13:30:00.000000000Z,1,1,10,A,17000.25,2,0,1,17000.00,17000.50,10,11,1,1,NQH4",
            "2024-01-08T13:30:01.000000000Z,2024-01-08T13:30:01.000000000Z,1,1,11,B,17001.00,1,0,2,17000.75,17001.25,8,9,1,1,NQH4-NQM4",
            "2024-01-08T13:30:02.000000000Z,,1,1,12,N,,0,0,3,17000.50,17001.00,5,5,1,1,NQH4",
        ],
    )

    frame = collect_sample_day(csv_path)

    assert frame.height == 2
    assert frame["symbol"].to_list() == ["NQH4", "NQH4"]
    assert frame["ts_recv"].dtype == pl.Datetime("ns", "UTC")


def test_missing_required_columns_raise(write_csv) -> None:
    csv_path = write_csv(
        "GLBX-20240109.csv",
        ["2024-01-09T13:30:00.000000000Z,2024-01-09T13:30:00.000000000Z,1,1,10,A,17000.25,2,0,1,17000.00,17000.50,10,11,1,1"],
    )

    with pytest.raises(ValueError, match="Missing required columns"):
        collect_sample_day(csv_path)


def test_missing_csv_path_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        collect_sample_day(tmp_path / "missing.csv")


def test_invalid_ts_recv_raises_parse_failure(write_csv) -> None:
    csv_path = write_csv(
        "GLBX-20240110.csv",
        [
            "not-a-timestamp,2024-01-10T13:30:00.000000000Z,1,1,10,A,17000.25,2,0,1,17000.00,17000.50,10,11,1,1,NQH4",
        ],
    )

    with pytest.raises(pl.exceptions.InvalidOperationError):
        collect_sample_day(csv_path)


def test_side_n_rows_allow_blank_trade_fields(write_csv) -> None:
    csv_path = write_csv(
        "GLBX-20240111.csv",
        [
            "2024-01-11T13:30:00.000000000Z,,1,1,10,N,,0,0,1,17000.00,17000.50,10,11,1,1,NQH4",
        ],
    )

    frame = collect_sample_day(csv_path)

    assert frame.height == 1
    assert frame["price"].to_list() == [None]
    assert frame["ts_event"].to_list() == [None]


def test_manifest_orders_by_date_then_name(write_csv, csv_root: Path) -> None:
    write_csv("GLBX-20240112-b.csv", [])
    write_csv("GLBX-20240111-a.csv", [])
    write_csv("GLBX-20240112-a.csv", [])

    manifest = build_manifest(csv_root)

    assert [entry.stem for entry in manifest] == [
        "GLBX-20240111-a",
        "GLBX-20240112-a",
        "GLBX-20240112-b",
    ]


def test_scan_candidate_outrights_only_keeps_outrights(write_csv) -> None:
    csv_path = write_csv(
        "GLBX-20240113.csv",
        [
            "2024-01-13T13:30:00.000000000Z,2024-01-13T13:30:00.000000000Z,1,1,10,A,17000.25,2,0,1,17000.00,17000.50,10,11,1,1,NQH4",
            "2024-01-13T13:30:01.000000000Z,2024-01-13T13:30:01.000000000Z,1,1,11,A,17001.00,1,0,2,17000.75,17001.25,8,9,1,1,ESH4",
            "2024-01-13T13:30:02.000000000Z,2024-01-13T13:30:02.000000000Z,1,1,12,A,17001.25,1,0,3,17001.00,17001.50,8,9,1,1,NQH4-NQM4",
        ],
    )

    frame = scan_candidate_outrights(csv_path).collect()

    assert frame["symbol"].to_list() == ["NQH4"]
