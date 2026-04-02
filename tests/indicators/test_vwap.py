from __future__ import annotations

from datetime import UTC, datetime

import polars as pl
import pytest

from vwap_revert.indicators.vwap import attach_daily_vwap_bands, compute_daily_vwap


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _session_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                datetime(2024, 1, 2).date(),
                datetime(2024, 1, 2).date(),
                datetime(2024, 1, 2).date(),
                datetime(2024, 1, 2).date(),
                datetime(2024, 1, 2).date(),
                datetime(2024, 1, 3).date(),
                datetime(2024, 1, 3).date(),
            ],
            "ts_recv": [
                _ts(2024, 1, 2, 14, 29, 59),
                _ts(2024, 1, 2, 14, 30, 0),
                _ts(2024, 1, 2, 14, 30, 1),
                _ts(2024, 1, 2, 14, 30, 2),
                _ts(2024, 1, 2, 14, 30, 3),
                _ts(2024, 1, 3, 14, 30, 0),
                _ts(2024, 1, 3, 14, 30, 1),
            ],
            "ts_recv_et": [
                _ts(2024, 1, 2, 9, 29, 59),
                _ts(2024, 1, 2, 9, 30, 0),
                _ts(2024, 1, 2, 9, 30, 1),
                _ts(2024, 1, 2, 9, 30, 2),
                _ts(2024, 1, 2, 9, 30, 3),
                _ts(2024, 1, 3, 9, 30, 0),
                _ts(2024, 1, 3, 9, 30, 1),
            ],
            "is_rth": [False, True, True, True, True, True, True],
            "side": ["A", "N", "B", "A", "N", "B", "A"],
            "price": [100.0, 101.0, 102.0, 104.0, 103.0, 200.0, 202.0],
            "size": [9.0, 5.0, 2.0, 3.0, 8.0, 1.0, 4.0],
        }
    )


def test_daily_vwap_uses_rth_trade_rows_only() -> None:
    result = compute_daily_vwap(_session_rows())

    assert result["ts_recv"].to_list() == [
        _ts(2024, 1, 2, 14, 30, 1),
        _ts(2024, 1, 2, 14, 30, 2),
        _ts(2024, 1, 3, 14, 30, 0),
        _ts(2024, 1, 3, 14, 30, 1),
    ]
    assert result["daily_vwap"].to_list() == [102.0, 103.2, 200.0, 201.6]
    assert result["cum_volume"].to_list() == [2.0, 5.0, 1.0, 5.0]
    assert result["cum_notional"].to_list() == [204.0, 516.0, 200.0, 1008.0]


def test_daily_vwap_resets_per_trading_date() -> None:
    result = compute_daily_vwap(_session_rows())

    first_session = result.filter(pl.col("trading_date") == datetime(2024, 1, 2).date())
    second_session = result.filter(pl.col("trading_date") == datetime(2024, 1, 3).date())

    assert first_session.row(0, named=True)["daily_vwap"] == 102.0
    assert second_session.row(0, named=True)["daily_vwap"] == 200.0
    assert second_session.row(0, named=True)["cum_volume"] == 1.0


def test_sigma_bands_use_volume_weighted_expanding_formula() -> None:
    result = attach_daily_vwap_bands(_session_rows())
    jan_2_rows = result.filter(pl.col("trading_date") == datetime(2024, 1, 2).date())

    second_trade = jan_2_rows.row(3, named=True)

    assert jan_2_rows.row(2, named=True)["daily_sigma"] == 0.0
    assert second_trade["cum_sq_notional"] == 53256.0
    assert second_trade["daily_sigma"] == pytest.approx(0.9797958971132712)
    assert second_trade["daily_vwap_upper_1s"] == pytest.approx(104.17979589711327)
    assert second_trade["daily_vwap_lower_4s"] == pytest.approx(99.28081641154691)


def test_indicator_columns_join_back_to_session_rows() -> None:
    result = attach_daily_vwap_bands(_session_rows())

    pre_trade_quote = result.row(1, named=True)
    first_trade = result.row(2, named=True)
    later_quote = result.row(4, named=True)

    assert pre_trade_quote["daily_vwap"] is None
    assert pre_trade_quote["daily_sigma"] is None
    assert first_trade["daily_vwap"] == 102.0
    assert first_trade["daily_sigma"] == 0.0
    assert later_quote["daily_vwap"] == pytest.approx(103.2)
    assert later_quote["daily_sigma"] == pytest.approx(0.9797958971132712)
    assert later_quote["daily_vwap_upper_4s"] == pytest.approx(107.11918358845308)
