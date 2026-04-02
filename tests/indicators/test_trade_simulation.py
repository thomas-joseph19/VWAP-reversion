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
    replay_single_trade,
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


def _path_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                date(2024, 1, 3),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 4),
                date(2024, 1, 4),
                date(2024, 1, 5),
                date(2024, 1, 5),
                date(2024, 1, 5),
                date(2024, 1, 5),
            ],
            "ts_recv": [
                _ts(2024, 1, 3, 14, 30, 0),
                _ts(2024, 1, 3, 14, 30, 1),
                _ts(2024, 1, 4, 14, 30, 0),
                _ts(2024, 1, 4, 14, 30, 1),
                _ts(2024, 1, 4, 14, 30, 2),
                _ts(2024, 1, 5, 20, 59, 59),
                _ts(2024, 1, 5, 21, 0, 0),
                _ts(2024, 1, 5, 21, 0, 1),
                _ts(2024, 1, 5, 21, 0, 2),
            ],
            "ts_recv_et": [
                _ts(2024, 1, 3, 9, 30, 0),
                _ts(2024, 1, 3, 9, 30, 1),
                _ts(2024, 1, 4, 9, 30, 0),
                _ts(2024, 1, 4, 9, 30, 1),
                _ts(2024, 1, 4, 9, 30, 2),
                _ts(2024, 1, 5, 15, 59, 59),
                _ts(2024, 1, 5, 16, 0, 0),
                _ts(2024, 1, 5, 16, 0, 1),
                _ts(2024, 1, 5, 16, 0, 2),
            ],
            "daily_vwap": [
                100.50,
                100.50,
                100.00,
                100.00,
                100.00,
                100.50,
                100.50,
                100.50,
                100.50,
            ],
            "bid_px_00": [
                100.00,
                100.50,
                99.75,
                94.75,
                94.50,
                100.00,
                100.00,
                100.75,
                101.00,
            ],
            "ask_px_00": [
                100.50,
                101.00,
                100.25,
                95.25,
                100.00,
                100.50,
                100.50,
                101.25,
                101.50,
            ],
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


def test_vwap_target_uses_executable_quote_side() -> None:
    setups = _setup_rows().to_dicts()
    path_rows = _path_rows()
    config = SimulationConfig()

    long_trade = replay_single_trade(open_trade_from_setup(setups[0], config), path_rows, config)
    short_trade = replay_single_trade(open_trade_from_setup(setups[1], config), path_rows, config)

    assert long_trade["exit_reason"] == "target_vwap"
    assert long_trade["exit_ts"] == _ts(2024, 1, 3, 14, 30, 1)
    assert long_trade["exit_price"] == 100.50
    assert long_trade["gross_points"] == 0.25

    assert short_trade["exit_reason"] == "target_vwap"
    assert short_trade["exit_ts"] == _ts(2024, 1, 4, 14, 30, 2)
    assert short_trade["exit_price"] == 100.00
    assert short_trade["gross_points"] == -0.25


def test_stop_loss_uses_executable_mae_and_adverse_first_ordering() -> None:
    config = SimulationConfig(stop_loss_points=5.0)
    short_setup = {
        "trading_date": date(2024, 1, 4),
        "ts_recv": _ts(2024, 1, 4, 14, 30, 1),
        "ts_recv_et": _ts(2024, 1, 4, 9, 30, 1),
        "setup_direction": "short",
        "daily_vwap": 100.0,
        "setup_sigma_signed": 2.0,
        "bid_px_00": 94.75,
        "ask_px_00": 95.00,
    }

    trade = replay_single_trade(open_trade_from_setup(short_setup, config), _path_rows(), config)

    assert trade["exit_reason"] == "stop_loss"
    assert trade["exit_ts"] == _ts(2024, 1, 4, 14, 30, 2)
    assert trade["exit_price"] == 100.00
    assert trade["mae_points"] == 5.0
    assert trade["gross_points"] == -5.25
    assert trade["duration_seconds"] == 1.0


def test_session_end_forces_exit_at_1600_et() -> None:
    config = SimulationConfig()
    long_setup = {
        "trading_date": date(2024, 1, 5),
        "ts_recv": _ts(2024, 1, 5, 20, 59, 59),
        "ts_recv_et": _ts(2024, 1, 5, 15, 59, 59),
        "setup_direction": "long",
        "daily_vwap": 100.50,
        "setup_sigma_signed": -2.0,
        "bid_px_00": 100.00,
        "ask_px_00": 100.25,
    }

    trade = replay_single_trade(open_trade_from_setup(long_setup, config), _path_rows(), config)

    assert trade["exit_reason"] == "session_end"
    assert trade["exit_ts"] == _ts(2024, 1, 5, 21, 0, 0)
    assert trade["exit_price"] == 100.00
    assert trade["duration_seconds"] == 1.0
