from __future__ import annotations

from datetime import date

import polars as pl

from vwap_revert.data_pipeline.quality import (
    build_quality_report,
    detect_day_gaps,
    detect_intraday_gaps,
)


def test_gap_detection_and_holiday_reporting() -> None:
    result = detect_day_gaps(
        trading_dates=[date(2024, 1, 2), date(2024, 1, 4)],
        expected_dates=[date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)],
        holiday_dates={date(2024, 1, 5)},
    )

    assert result["missing_trading_dates"] == [date(2024, 1, 3)]
    assert result["holiday_dates"] == [date(2024, 1, 5)]


def test_structural_vs_recoverable_errors() -> None:
    frame = pl.DataFrame(
        {
            "trading_date": [date(2024, 1, 2), date(2024, 1, 2)],
            "session_name": ["rth", "rth"],
            "is_rth": [True, True],
            "ts_recv_et": [
                "2024-01-02T09:30:00-05:00",
                "2024-01-02T09:36:10-05:00",
            ],
        }
    ).with_columns(pl.col("ts_recv_et").str.strptime(pl.Datetime("ns", "America/New_York"), strict=True))

    intraday_gaps = detect_intraday_gaps(frame)
    report = build_quality_report(
        trading_dates=[date(2024, 1, 2)],
        expected_dates=[date(2024, 1, 2)],
        holiday_dates=set(),
        intraday_gaps=intraday_gaps,
        recoverable_row_issues={"dropped_rows": 2},
        examples={"dropped_rows": ["2024-01-02T09:35:00-05:00"]},
        contract_map=pl.DataFrame(
            {
                "trading_date": [date(2024, 1, 2)],
                "front_symbol": ["NQH4"],
                "trade_volume": [10.0],
                "is_roll": [False],
                "prior_symbol": [None],
            }
        ),
        session_df=frame,
    )

    assert intraday_gaps["gap_seconds"].to_list() == [370]
    assert report["recoverable_row_issues"] == {"dropped_rows": 2}
    assert report["examples"] == {"dropped_rows": ["2024-01-02T09:35:00-05:00"]}
    assert report["unusable_days"] == ["2024-01-02"]

