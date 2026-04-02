"""Phase 05 trade-simulation primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from math import isnan
from typing import Mapping

import polars as pl


@dataclass(frozen=True)
class SimulationConfig:
    stop_loss_points: float = 20.0
    round_trip_commission: float = 5.0
    additional_slippage_points: float = 0.0
    point_value: float = 20.0
    tick_size: float = 0.25
    tick_value: float = 5.0
    session_exit_time: time = time(16, 0)


@dataclass(frozen=True)
class SimulationBatchResult:
    trade_log: pl.DataFrame
    skipped_setups: pl.DataFrame


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


def _require_datetime(row: Mapping[str, object], column: str) -> datetime:
    value = row.get(column)
    if value is None or not isinstance(value, datetime):
        raise ValueError(f"{column} is required")
    return value


def _output_trade_columns() -> list[str]:
    return [
        "trading_date",
        "direction",
        "signal_ts",
        "entry_ts",
        "entry_price",
        "exit_ts",
        "exit_price",
        "exit_reason",
        "target_price",
        "gross_points",
        "net_dollars",
        "mae_points",
        "duration_seconds",
        "setup_sigma_signed",
    ]


def _skipped_setup_schema() -> dict[str, pl.DataType]:
    return {
        "trading_date": pl.Date,
        "ts_recv": pl.Datetime(time_unit="us", time_zone="UTC"),
        "setup_direction": pl.Utf8,
        "setup_sigma_signed": pl.Float64,
        "skip_reason": pl.Utf8,
    }


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


def replay_single_trade(
    trade: Mapping[str, object],
    path_rows: pl.DataFrame,
    config: SimulationConfig,
) -> dict[str, object]:
    direction = _normalize_direction(str(trade.get("direction")))
    trading_date = trade.get("trading_date")
    entry_ts = _require_datetime(trade, "entry_ts")
    signal_ts = _require_datetime(trade, "signal_ts")
    entry_price = float(trade.get("entry_price", 0.0))
    target_price = float(trade.get("target_price", 0.0))
    stop_loss_points = float(trade.get("stop_loss_points", config.stop_loss_points))
    additional_slippage_points = float(
        trade.get("additional_slippage_points", config.additional_slippage_points)
    )
    round_trip_commission = float(trade.get("round_trip_commission", config.round_trip_commission))
    setup_sigma_signed = float(trade.get("setup_sigma_signed", 0.0))

    ordered_rows = path_rows.sort(["trading_date", "ts_recv"]).filter(
        (pl.col("trading_date") == trading_date) & (pl.col("ts_recv") >= entry_ts)
    )
    if ordered_rows.is_empty():
        raise ValueError("No replay rows available for trade")

    mae_points = 0.0
    session_end_row: Mapping[str, object] | None = None

    for row in ordered_rows.iter_rows(named=True):
        ts_recv_et = _require_datetime(row, "ts_recv_et")
        exit_side_price = _require_price(
            row,
            "bid_px_00" if direction == "long" else "ask_px_00",
        )
        adverse_move = max(
            0.0,
            entry_price - exit_side_price if direction == "long" else exit_side_price - entry_price,
        )
        mae_points = max(mae_points, adverse_move)

        target_hit = (
            exit_side_price >= target_price if direction == "long" else exit_side_price <= target_price
        )
        stop_hit = adverse_move >= stop_loss_points
        if stop_hit or target_hit:
            exit_reason = "stop_loss" if stop_hit else "target_vwap"
            exit_price = exit_fill_price(
                row,
                direction,
                additional_slippage_points=additional_slippage_points,
            )
            exit_ts = _require_datetime(row, "ts_recv")
            gross_points = pnl_points(direction, entry_price, exit_price)
            return {
                "trading_date": trading_date,
                "direction": direction,
                "signal_ts": signal_ts,
                "entry_ts": entry_ts,
                "entry_price": entry_price,
                "exit_ts": exit_ts,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "target_price": target_price,
                "gross_points": gross_points,
                "net_dollars": pnl_dollars(
                    direction,
                    entry_price,
                    exit_price,
                    point_value=config.point_value,
                    round_trip_commission=round_trip_commission,
                ),
                "mae_points": mae_points,
                "duration_seconds": (exit_ts - entry_ts).total_seconds(),
                "setup_sigma_signed": setup_sigma_signed,
            }

        if ts_recv_et.timetz().replace(tzinfo=None) >= config.session_exit_time:
            session_end_row = row
            break

    if session_end_row is None:
        raise ValueError("Trade remained open without a session-end liquidation row")

    exit_price = exit_fill_price(
        session_end_row,
        direction,
        additional_slippage_points=additional_slippage_points,
    )
    exit_ts = _require_datetime(session_end_row, "ts_recv")
    gross_points = pnl_points(direction, entry_price, exit_price)
    return {
        "trading_date": trading_date,
        "direction": direction,
        "signal_ts": signal_ts,
        "entry_ts": entry_ts,
        "entry_price": entry_price,
        "exit_ts": exit_ts,
        "exit_price": exit_price,
        "exit_reason": "session_end",
        "target_price": target_price,
        "gross_points": gross_points,
        "net_dollars": pnl_dollars(
            direction,
            entry_price,
            exit_price,
            point_value=config.point_value,
            round_trip_commission=round_trip_commission,
        ),
        "mae_points": mae_points,
        "duration_seconds": (exit_ts - entry_ts).total_seconds(),
        "setup_sigma_signed": setup_sigma_signed,
    }


def simulate_trades(
    setup_log: pl.DataFrame,
    path_rows: pl.DataFrame,
    config: SimulationConfig,
) -> SimulationBatchResult:
    completed_trades: list[dict[str, object]] = []
    skipped_setups: list[dict[str, object]] = []
    active_exit_ts: datetime | None = None

    for setup in setup_log.sort(["trading_date", "ts_recv"]).iter_rows(named=True):
        setup_ts = _require_datetime(setup, "ts_recv")
        if active_exit_ts is not None and setup_ts <= active_exit_ts:
            skipped_setups.append(
                {
                    "trading_date": setup.get("trading_date"),
                    "ts_recv": setup_ts,
                    "setup_direction": str(setup.get("setup_direction")),
                    "setup_sigma_signed": float(setup.get("setup_sigma_signed", 0.0)),
                    "skip_reason": "position_active",
                }
            )
            continue

        replayed_trade = replay_single_trade(open_trade_from_setup(setup, config), path_rows, config)
        completed_trades.append(replayed_trade)
        active_exit_ts = replayed_trade["exit_ts"]

    trade_log = (
        pl.DataFrame(completed_trades).select(_output_trade_columns()).sort("entry_ts")
        if completed_trades
        else pl.DataFrame(schema={column: pl.Null for column in _output_trade_columns()}).select(
            _output_trade_columns()
        )
    )
    skipped_df = (
        pl.DataFrame(skipped_setups, schema=_skipped_setup_schema())
        if skipped_setups
        else pl.DataFrame(schema=_skipped_setup_schema())
    ).select(list(_skipped_setup_schema().keys()))

    return SimulationBatchResult(trade_log=trade_log, skipped_setups=skipped_df)


__all__ = [
    "SimulationConfig",
    "SimulationBatchResult",
    "entry_fill_price",
    "exit_fill_price",
    "open_trade_from_setup",
    "pnl_points",
    "pnl_dollars",
    "replay_single_trade",
    "simulate_trades",
]
