from __future__ import annotations

from datetime import date

import polars as pl

from vwap_revert.data_pipeline.sessions import add_eastern_timestamps, label_sessions


def test_dst_transition_dates() -> None:
    frame = pl.DataFrame(
        {
            "ts_recv": [
                "2024-03-10T06:59:59.000000000Z",
                "2024-03-10T07:00:00.000000000Z",
                "2024-11-03T05:59:59.000000000Z",
                "2024-11-03T06:00:00.000000000Z",
            ]
        }
    ).with_columns(pl.col("ts_recv").str.strptime(pl.Datetime("ns", "UTC"), strict=True))

    localized = add_eastern_timestamps(frame)

    assert localized["ts_recv_et"].dt.strftime("%Y-%m-%d %H:%M:%S%:z").to_list() == [
        "2024-03-10 01:59:59-05:00",
        "2024-03-10 03:00:00-04:00",
        "2024-11-03 01:59:59-04:00",
        "2024-11-03 01:00:00-05:00",
    ]


def test_globex_boundary_labels() -> None:
    frame = pl.DataFrame(
        {
            "ts_recv": [
                "2024-03-08T22:00:00.000000000Z",
                "2024-03-08T23:00:00.000000000Z",
                "2024-03-09T15:00:00.000000000Z",
            ]
        }
    ).with_columns(pl.col("ts_recv").str.strptime(pl.Datetime("ns", "UTC"), strict=True))

    labeled = label_sessions(add_eastern_timestamps(frame))

    assert labeled["session_name"].to_list() == ["maintenance", "overnight", "rth"]
    assert labeled["trading_date"].to_list() == [
        date(2024, 3, 8),
        date(2024, 3, 9),
        date(2024, 3, 9),
    ]
    assert labeled["is_rth"].to_list() == [False, False, True]
    assert labeled["is_overnight"].to_list() == [False, True, False]
    assert labeled["is_maintenance"].to_list() == [True, False, False]
