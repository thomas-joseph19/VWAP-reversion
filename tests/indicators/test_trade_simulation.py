from __future__ import annotations

from datetime import UTC, date, datetime, time

import polars as pl

from vwap_revert.simulation import (
    SimulationConfig,
    entry_fill_price,
    exit_fill_price,
    open_trade_from_setup,
    pnl_dollars,
    pnl_points,
)


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _setup_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [date(2024, 1, 3), date(2024, 1, 3)],
            "ts_recv": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 30, 1)],
            "ts_recv_et": [_ts(2024, 1, 3, 9, 30, 0), _ts(2024, 1, 3, 9, 30, 1)],
            "setup_direction": ["long", "short"],
            "daily_vwap": [100.0, 100.0],
            "setup_sigma_signed": [-2.0, 2.0],
            "bid_px_00": [100.00, 99.75],
            "ask_px_00": [100.25, 100.00],
        },
        strict=False,
    )


def test_enters_immediately_from_setup_event() -> None:
    setups = _setup_rows().to_dicts()
    config = SimulationConfig()

    assert config.round_trip_commission == 5.0
    assert config.additional_slippage_points == 0.0
    assert config.point_value == 20.0
    assert config.session_exit_time == time(16, 0)

    long_trade = open_trade_from_setup(setups[0], config)
    short_trade = open_trade_from_setup(setups[1], config)

    assert long_trade["direction"] == "long"
    assert long_trade["signal_ts"] == setups[0]["ts_recv"]
    assert long_trade["entry_ts"] == setups[0]["ts_recv"]
    assert long_trade["entry_price"] == 100.25
    assert long_trade["target_price"] == 100.0
    assert long_trade["trading_date"] == setups[0]["trading_date"]
    assert long_trade["daily_vwap"] == 100.0
    assert long_trade["setup_sigma_signed"] == -2.0
    assert long_trade["status"] == "open"
    assert long_trade["entry_reason"] == "setup_event"

    assert short_trade["direction"] == "short"
    assert short_trade["signal_ts"] == setups[1]["ts_recv"]
    assert short_trade["entry_ts"] == setups[1]["ts_recv"]
    assert short_trade["entry_price"] == 99.75
    assert short_trade["target_price"] == 100.0
    assert short_trade["status"] == "open"
    assert short_trade["entry_reason"] == "setup_event"


def test_fill_prices_apply_bbo_side_and_additional_impact() -> None:
    long_row, short_row = _setup_rows().to_dicts()

    assert entry_fill_price(long_row, "long") == 100.25
    assert entry_fill_price(short_row, "short") == 99.75
    assert exit_fill_price(long_row, "long") == 100.0
    assert exit_fill_price(short_row, "short") == 100.0

    assert entry_fill_price(long_row, "long", additional_slippage_points=0.50) == 100.75
    assert entry_fill_price(short_row, "short", additional_slippage_points=0.50) == 99.25
    assert exit_fill_price(long_row, "long", additional_slippage_points=0.50) == 99.50
    assert exit_fill_price(short_row, "short", additional_slippage_points=0.50) == 100.50


def test_round_trip_commission_reduces_net_pnl() -> None:
    assert pnl_points("long", entry_price=100.25, exit_price=101.25) == 1.0
    assert pnl_dollars(
        "long",
        entry_price=100.25,
        exit_price=101.25,
        point_value=20.0,
        round_trip_commission=5.0,
    ) == 15.0

    assert pnl_points("short", entry_price=100.00, exit_price=99.00) == 1.0
    assert pnl_dollars(
        "short",
        entry_price=100.00,
        exit_price=99.00,
        point_value=20.0,
        round_trip_commission=5.0,
    ) == 15.0
