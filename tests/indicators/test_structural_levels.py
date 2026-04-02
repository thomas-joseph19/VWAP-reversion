from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl

from vwap_revert.indicators.structural_levels import (
    attach_prior_day_structural_levels,
    compute_prior_day_structural_levels,
)


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _usable_structural_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 3),
                date(2024, 1, 3),
            ],
            "ts_recv": [
                _ts(2024, 1, 2, 14, 29, 59),
                _ts(2024, 1, 2, 14, 30, 0),
                _ts(2024, 1, 2, 14, 30, 1),
                _ts(2024, 1, 2, 14, 30, 2),
                _ts(2024, 1, 2, 14, 30, 3),
                _ts(2024, 1, 3, 14, 30, 0),
                _ts(2024, 1, 3, 14, 30, 1),
                _ts(2024, 1, 3, 14, 30, 2),
            ],
            "is_rth": [False, True, True, True, True, True, True, True],
            "side": ["A", "B", "A", "B", "N", "B", "N", "B"],
            "price": [99.0, 100.0, 101.0, 102.0, 103.0, 111.0, 89.0, 110.0],
            "size": [999.0, 50.0, 20.0, 50.0, 700.0, 3.0, 0.0, 4.0],
            "bid_px_00": [None, 99.75, 100.75, 101.75, 102.5, 110.75, 89.0, 109.75],
            "ask_px_00": [None, 100.25, 101.25, 102.25, 103.5, 111.25, None, 110.25],
        },
        strict=False,
    )


def _quality_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 4),
                date(2024, 1, 4),
                date(2024, 1, 5),
                date(2024, 1, 5),
                date(2024, 1, 6),
            ],
            "ts_recv": [
                _ts(2024, 1, 2, 14, 30, 0),
                _ts(2024, 1, 2, 14, 30, 1),
                _ts(2024, 1, 4, 14, 30, 0),
                _ts(2024, 1, 4, 14, 30, 1),
                _ts(2024, 1, 5, 14, 30, 0),
                _ts(2024, 1, 5, 14, 30, 1),
                _ts(2024, 1, 6, 14, 30, 0),
            ],
            "is_rth": [True, True, True, True, True, True, True],
            "side": ["B", "A", "B", "N", "N", "N", "B"],
            "price": [100.0, 101.0, 111.0, 109.0, 100.0, 100.0, 110.0],
            "size": [5.0, 7.0, 3.0, 0.0, 0.0, 0.0, 4.0],
            "bid_px_00": [99.75, 100.75, 110.75, 108.75, 99.75, 99.5, 109.75],
            "ask_px_00": [100.25, 101.25, 111.25, 109.25, 100.25, 100.5, 110.25],
        },
        strict=False,
    )


def test_prior_day_levels_use_rth_trade_rows_only() -> None:
    result = compute_prior_day_structural_levels(_usable_structural_rows())

    jan_3 = result.filter(pl.col("trading_date") == date(2024, 1, 3)).row(0, named=True)

    assert jan_3["source_trading_date"] == date(2024, 1, 2)
    assert jan_3["prior_rth_poc"] == 100.0
    assert jan_3["prior_rth_val"] == 100.0
    assert jan_3["prior_rth_vah"] == 102.0
    assert jan_3["levels_available"] is True
    assert jan_3["quality_status"] == "ok"
    assert jan_3["profile_trade_rows"] == 3
    assert jan_3["profile_total_volume"] == 120.0


def test_missing_immediately_prior_session_emits_null_levels() -> None:
    result = compute_prior_day_structural_levels(_quality_rows())

    jan_4 = result.filter(pl.col("trading_date") == date(2024, 1, 4)).row(0, named=True)
    jan_6 = result.filter(pl.col("trading_date") == date(2024, 1, 6)).row(0, named=True)

    assert jan_4["source_trading_date"] == date(2024, 1, 3)
    assert jan_4["prior_rth_vah"] is None
    assert jan_4["prior_rth_val"] is None
    assert jan_4["prior_rth_poc"] is None
    assert jan_4["levels_available"] is False
    assert jan_4["quality_status"] == "missing_prior_session"

    assert jan_6["source_trading_date"] == date(2024, 1, 5)
    assert jan_6["prior_rth_vah"] is None
    assert jan_6["prior_rth_val"] is None
    assert jan_6["prior_rth_poc"] is None
    assert jan_6["levels_available"] is False
    assert jan_6["quality_status"] == "unusable_prior_session"
    assert jan_6["profile_trade_rows"] == 0
    assert jan_6["profile_total_volume"] == 0.0


def test_proximity_features_use_inclusive_threshold() -> None:
    result = attach_prior_day_structural_levels(_usable_structural_rows(), proximity_threshold_points=10.0)

    jan_3_trade = result.filter(
        (pl.col("trading_date") == date(2024, 1, 3)) & (pl.col("ts_recv") == _ts(2024, 1, 3, 14, 30, 0))
    ).row(0, named=True)
    jan_3_bid_only = result.filter(
        (pl.col("trading_date") == date(2024, 1, 3)) & (pl.col("ts_recv") == _ts(2024, 1, 3, 14, 30, 1))
    ).row(0, named=True)

    assert jan_3_trade["structural_reference_price"] == 111.0
    assert jan_3_trade["distance_to_prior_rth_vah"] == 9.0
    assert jan_3_trade["distance_to_prior_rth_val"] == 11.0
    assert jan_3_trade["distance_to_prior_rth_poc"] == 11.0
    assert jan_3_trade["near_prior_rth_vah"] is True
    assert jan_3_trade["near_prior_rth_val"] is False
    assert jan_3_trade["near_prior_rth_poc"] is False
    assert jan_3_trade["nearest_structural_level"] == "prior_rth_vah"
    assert jan_3_trade["nearest_structural_distance"] == 9.0
    assert jan_3_trade["structural_levels_within_threshold"] == 1

    assert jan_3_bid_only["structural_reference_price"] == 89.0
    assert jan_3_bid_only["distance_to_prior_rth_vah"] == -13.0
    assert jan_3_bid_only["distance_to_prior_rth_val"] == -11.0
    assert jan_3_bid_only["distance_to_prior_rth_poc"] == -11.0
    assert jan_3_bid_only["near_prior_rth_vah"] is False
    assert jan_3_bid_only["near_prior_rth_val"] is False
    assert jan_3_bid_only["near_prior_rth_poc"] is False
    assert jan_3_bid_only["nearest_structural_level"] == "prior_rth_val"
    assert jan_3_bid_only["nearest_structural_distance"] == 11.0
    assert jan_3_bid_only["structural_levels_within_threshold"] == 0

