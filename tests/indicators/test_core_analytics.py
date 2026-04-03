from __future__ import annotations

from datetime import UTC, date, datetime
from math import isclose

import polars as pl

from vwap_revert.analytics import compute_performance_metrics, prepare_trade_log


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _phase5_trade_log_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [date(2024, 1, 3), date(2024, 1, 3)],
            "direction": ["long", "short"],
            "signal_ts": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 45, 0)],
            "entry_ts": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 45, 0)],
            "entry_price": [100.25, 101.75],
            "exit_ts": [_ts(2024, 1, 3, 14, 35, 0), _ts(2024, 1, 3, 14, 50, 0)],
            "exit_price": [101.25, 102.25],
            "exit_reason": ["target_vwap", "stop_loss"],
            "target_price": [101.0, 101.0],
            "gross_points": [1.0, -0.5],
            "net_dollars": [15.0, -15.0],
            "mae_points": [0.25, 0.5],
            "duration_seconds": [300.0, 300.0],
            "setup_sigma_signed": [-2.1, 2.3],
            "nearest_structural_level": ["prior_rth_val", "prior_rth_vah"],
            "nearest_structural_distance": [1.5, 1.0],
            "regime_label": ["balanced", "trend"],
            "regime_reason": ["fixture", "fixture"],
        },
        strict=False,
    )


def test_prepare_trade_log_adds_ticks_and_preserves_phase5_context() -> None:
    prepared = prepare_trade_log(_phase5_trade_log_fixture())

    assert prepared.height == 2
    assert prepared["entry_ts"].to_list() == sorted(prepared["entry_ts"].to_list())
    assert "pnl_points" in prepared.columns
    assert "pnl_ticks" in prepared.columns
    assert "sigma_at_entry" in prepared.columns
    assert "entry_price" in prepared.columns
    assert "exit_price" in prepared.columns
    assert "net_dollars" in prepared.columns
    assert "duration_seconds" in prepared.columns
    assert "nearest_structural_level" in prepared.columns
    assert "regime_label" in prepared.columns

    rows = list(prepared.iter_rows(named=True))
    assert isclose(rows[0]["pnl_points"], 1.0)
    assert isclose(rows[0]["pnl_ticks"], 4.0)
    assert isclose(rows[1]["pnl_points"], -0.5)
    assert isclose(rows[1]["pnl_ticks"], -2.0)
    assert rows[0]["sigma_at_entry"] == -2.1
    assert rows[1]["sigma_at_entry"] == 2.3
    assert rows[0]["nearest_structural_level"] == "prior_rth_val"
    assert rows[1]["regime_label"] == "trend"


def test_compute_performance_metrics_handles_wins_losses_drawdown_and_sharpe_edges() -> None:
    trade_log = pl.DataFrame(
        {
            "entry_ts": [
                _ts(2024, 1, 3, 14, 30, 0),
                _ts(2024, 1, 3, 14, 35, 0),
                _ts(2024, 1, 3, 14, 40, 0),
            ],
            "net_dollars": [15.0, -25.0, 35.0],
        }
    )

    metrics = compute_performance_metrics(trade_log)

    assert metrics["trade_count"] == 3
    assert metrics["wins"] == 2
    assert metrics["losses"] == 1
    assert metrics["total_net_dollars"] == 25.0
    assert metrics["average_win_dollars"] == 25.0
    assert metrics["average_loss_dollars"] == -25.0
    assert metrics["average_win_loss_ratio"] == 1.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["max_drawdown_dollars"] == 25.0
    assert metrics["sharpe_ratio"] is not None

    one_trade_metrics = compute_performance_metrics(
        pl.DataFrame({"entry_ts": [_ts(2024, 1, 3, 14, 30, 0)], "net_dollars": [12.0]})
    )
    assert one_trade_metrics["sharpe_ratio"] is None

    zero_variance_metrics = compute_performance_metrics(
        pl.DataFrame(
            {
                "entry_ts": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 35, 0)],
                "net_dollars": [10.0, 10.0],
            }
        )
    )
    assert zero_variance_metrics["sharpe_ratio"] is None

    no_loss_metrics = compute_performance_metrics(
        pl.DataFrame(
            {
                "entry_ts": [_ts(2024, 1, 3, 14, 30, 0), _ts(2024, 1, 3, 14, 35, 0)],
                "net_dollars": [10.0, 15.0],
            }
        )
    )
    assert no_loss_metrics["profit_factor"] is None
