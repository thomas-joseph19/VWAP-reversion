"""Phase 05 trade-simulation primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from math import isnan
from typing import Mapping


@dataclass(frozen=True)
class SimulationConfig:
    stop_loss_points: float = 20.0
    round_trip_commission: float = 5.0
    additional_slippage_points: float = 0.0
    point_value: float = 20.0
    tick_size: float = 0.25
    tick_value: float = 5.0
    session_exit_time: time = time(16, 0)


def _normalize_direction(direction: str) -> str:
    if direction not in {"long", "short"}:
        raise ValueError("direction must be exactly 'long' or 'short'")
    return direction


def _require_price(row: Mapping[str, object], column: str) -> float:
    value = row.get(column)
    if value is None:
        raise ValueError(f"{column} is required")

    price = float(value)
    if isnan(price):
        raise ValueError(f"{column} is required")
    return price


def entry_fill_price(
    row: Mapping[str, object],
    direction: str,
    additional_slippage_points: float = 0.0,
) -> float:
    normalized_direction = _normalize_direction(direction)
    if normalized_direction == "long":
        return _require_price(row, "ask_px_00") + additional_slippage_points
    return _require_price(row, "bid_px_00") - additional_slippage_points


def exit_fill_price(
    row: Mapping[str, object],
    direction: str,
    additional_slippage_points: float = 0.0,
) -> float:
    normalized_direction = _normalize_direction(direction)
    if normalized_direction == "long":
        return _require_price(row, "bid_px_00") - additional_slippage_points
    return _require_price(row, "ask_px_00") + additional_slippage_points


def pnl_points(direction: str, entry_price: float, exit_price: float) -> float:
    normalized_direction = _normalize_direction(direction)
    if normalized_direction == "long":
        return exit_price - entry_price
    return entry_price - exit_price


def pnl_dollars(
    direction: str,
    entry_price: float,
    exit_price: float,
    point_value: float,
    round_trip_commission: float,
) -> float:
    return (pnl_points(direction, entry_price, exit_price) * point_value) - round_trip_commission


def open_trade_from_setup(setup: Mapping[str, object], config: SimulationConfig) -> dict[str, object]:
    direction = _normalize_direction(str(setup.get("setup_direction")))
    signal_ts = setup.get("ts_recv")
    trading_date = setup.get("trading_date")
    daily_vwap = setup.get("daily_vwap")
    setup_sigma_signed = setup.get("setup_sigma_signed")
    if signal_ts is None:
        raise ValueError("ts_recv is required")
    if trading_date is None:
        raise ValueError("trading_date is required")
    if daily_vwap is None:
        raise ValueError("daily_vwap is required")
    if setup_sigma_signed is None:
        raise ValueError("setup_sigma_signed is required")

    return {
        "trading_date": trading_date,
        "direction": direction,
        "entry_ts": signal_ts,
        "entry_price": entry_fill_price(
            setup,
            direction,
            additional_slippage_points=config.additional_slippage_points,
        ),
        "signal_ts": signal_ts,
        "target_price": float(daily_vwap),
        "daily_vwap": float(daily_vwap),
        "setup_sigma_signed": float(setup_sigma_signed),
        "stop_loss_points": config.stop_loss_points,
        "round_trip_commission": config.round_trip_commission,
        "additional_slippage_points": config.additional_slippage_points,
        "status": "open",
        "entry_reason": "setup_event",
    }


__all__ = [
    "SimulationConfig",
    "entry_fill_price",
    "exit_fill_price",
    "open_trade_from_setup",
    "pnl_points",
    "pnl_dollars",
]
