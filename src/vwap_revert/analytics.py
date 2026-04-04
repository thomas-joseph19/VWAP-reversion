"""Phase 06 core analytics helpers and artifact writing."""

from __future__ import annotations

import json
from math import sqrt
from pathlib import Path

import polars as pl


PHASE5_TRADE_LOG_ARTIFACT_NAME = "phase5_trade_log.parquet"
PHASE6_TRADE_LOG_CSV_NAME = "phase6_trade_log.csv"
PHASE6_METRICS_JSON_NAME = "phase6_metrics.json"
PHASE6_VALIDATION_EXPORT_NAME = "core_analytics_validation_export.csv"
PHASE6_VALIDATION_MANIFEST_NAME = "validation_sessions.json"

PHASE10_ANALYTICS_REPORT_NAME = "phase10_analytics_report.json"
PHASE10_EQUITY_CURVE_NAME = "phase10_equity_curve.parquet"

DEFAULT_TICK_SIZE = 0.25
SHARPE_CONVENTION = "mean(net_dollars) / sample_std(net_dollars) * sqrt(trade_count); null if trade_count < 2 or std == 0"


def prepare_trade_log(trade_log: pl.DataFrame, tick_size: float = DEFAULT_TICK_SIZE) -> pl.DataFrame:
    """Prepare the Phase 5 trade log for analyst-facing exports."""

    if tick_size <= 0:
        raise ValueError("tick_size must be positive")

    prepared = trade_log.with_columns(
        pl.col("gross_points").alias("pnl_points"),
        (pl.col("gross_points") / tick_size).alias("pnl_ticks"),
        pl.col("setup_sigma_signed").alias("sigma_at_entry"),
    ).with_columns(
        pl.when(pl.col("sigma_at_entry").abs() < 2.2)
        .then(pl.lit("1.7-2.2"))
        .when(pl.col("sigma_at_entry").abs() < 3.0)
        .then(pl.lit("2.2-3.0"))
        .otherwise(pl.lit("3.0+"))
        .alias("sigma_band"),
        pl.col("entry_ts").dt.truncate("15m").dt.time().alias("time_bucket_15m"),
    )
    return prepared.sort("entry_ts")


def compute_performance_metrics(trade_log: pl.DataFrame) -> dict[str, object]:
    """Compute deterministic baseline performance metrics from Phase 5 net dollars."""

    if trade_log.is_empty():
        return {
            "trade_count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "average_win_dollars": None,
            "average_loss_dollars": None,
            "average_win_loss_ratio": None,
            "profit_factor": None,
            "max_drawdown_dollars": 0.0,
            "sharpe_ratio": None,
            "total_net_dollars": 0.0,
        }

    ordered = trade_log.sort("entry_ts")
    net_values = [float(value) for value in ordered["net_dollars"].to_list()]
    trade_count = len(net_values)
    winning_values = [value for value in net_values if value > 0]
    losing_values = [value for value in net_values if value < 0]
    wins = len(winning_values)
    losses = len(losing_values)

    average_win = sum(winning_values) / wins if wins else None
    average_loss = sum(losing_values) / losses if losses else None
    average_win_loss_ratio = (
        average_win / abs(average_loss)
        if average_win is not None and average_loss is not None and average_loss != 0
        else None
    )

    gross_profit = sum(winning_values)
    gross_loss = abs(sum(losing_values))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    cumulative = 0.0
    running_peak = 0.0
    max_drawdown = 0.0
    for value in net_values:
        cumulative += value
        running_peak = max(running_peak, cumulative)
        max_drawdown = max(max_drawdown, running_peak - cumulative)

    sharpe_ratio = _compute_sharpe_ratio(net_values)
    total_net_dollars = sum(net_values)

    return {
        "trade_count": trade_count,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / trade_count if trade_count else None,
        "average_win_dollars": average_win,
        "average_loss_dollars": average_loss,
        "average_win_loss_ratio": average_win_loss_ratio,
        "profit_factor": profit_factor,
        "max_drawdown_dollars": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "total_net_dollars": total_net_dollars,
    }


def compute_performance_breakdowns(trade_log: pl.DataFrame) -> dict[str, dict[str, object]]:
    """Compute performance metrics grouped by regime, sigma band, and time-of-day."""
    
    breakdowns = {}
    
    dimensions = ["regime_label", "sigma_band", "time_bucket_15m"]
    for dim in dimensions:
        if dim not in trade_log.columns:
            continue
            
        group_stats = (
            trade_log.group_by(dim)
            .agg([
                pl.len().alias("trade_count"),
                pl.col("net_dollars").filter(pl.col("net_dollars") > 0).len().alias("wins"),
                pl.col("net_dollars").filter(pl.col("net_dollars") < 0).len().alias("losses"),
                pl.col("net_dollars").filter(pl.col("net_dollars") > 0).sum().alias("gross_profit"),
                pl.col("net_dollars").filter(pl.col("net_dollars") < 0).sum().abs().alias("gross_loss"),
                pl.col("net_dollars").sum().alias("total_net_dollars"),
                pl.col("net_dollars").mean().alias("avg_net_dollars"),
            ])
            .with_columns([
                (pl.col("wins") / pl.col("trade_count")).alias("win_rate"),
                (pl.col("gross_profit") / pl.col("gross_loss")).alias("profit_factor"),
            ])
            .sort(dim)
        )
        
        # Convert to dictionary with string keys (especially for time buckets)
        breakdowns[dim] = {
            str(row[dim]): {
                k: v for k, v in row.items() if k != dim
            }
            for row in group_stats.to_dicts()
        }
    
    return breakdowns


def write_core_analytics_artifacts(
    phase5_root: Path,
    output_root: Path,
    validation_dates: list[str],
    tick_size: float = DEFAULT_TICK_SIZE,
) -> tuple[Path, Path]:
    """Write deterministic Phase 6 CSV/JSON analytics artifacts and validation outputs."""

    normalized_dates = sorted(dict.fromkeys(validation_dates))
    if not normalized_dates:
        raise ValueError("validation_dates must include at least one YYYY-MM-DD value")

    output_root.mkdir(parents=True, exist_ok=True)
    validation_dir = output_root / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    phase5_trade_log = pl.read_parquet(phase5_root / PHASE5_TRADE_LOG_ARTIFACT_NAME)
    prepared_trade_log = prepare_trade_log(phase5_trade_log, tick_size=tick_size)
    metrics = compute_performance_metrics(prepared_trade_log)
    breakdowns = compute_performance_breakdowns(prepared_trade_log)
    
    # 1. Core artifacts
    trade_log_csv_path = output_root / PHASE6_TRADE_LOG_CSV_NAME
    metrics_json_path = output_root / PHASE6_METRICS_JSON_NAME
    prepared_trade_log.write_csv(trade_log_csv_path)
    metrics_json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    
    # 2. Phase 10 artifacts
    report = {
        "overall": metrics,
        "breakdowns": breakdowns,
    }
    report_path = output_root / PHASE10_ANALYTICS_REPORT_NAME
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    
    equity_curve = (
        prepared_trade_log.select(["entry_ts", "net_dollars"])
        .with_columns(pl.col("net_dollars").cum_sum().alias("cumulative_pnl_dollars"))
    )
    equity_curve_path = output_root / PHASE10_EQUITY_CURVE_NAME
    equity_curve.write_parquet(equity_curve_path)

    # 3. Validation
    validation_export = (
        prepared_trade_log.with_columns(pl.col("trading_date").cast(pl.Utf8))
        .filter(pl.col("trading_date").is_in(normalized_dates))
        .sort(["trading_date", "entry_ts"])
    )
    validation_export_path = validation_dir / PHASE6_VALIDATION_EXPORT_NAME
    validation_export.write_csv(validation_export_path)

    manifest = {
        "phase5_trade_log_artifact": PHASE5_TRADE_LOG_ARTIFACT_NAME,
        "trade_log_csv_artifact": PHASE6_TRADE_LOG_CSV_NAME,
        "metrics_json_artifact": PHASE6_METRICS_JSON_NAME,
        "phase10_analytics_report": PHASE10_ANALYTICS_REPORT_NAME,
        "phase10_equity_curve": PHASE10_EQUITY_CURVE_NAME,
        "validation_export": f"validation/{PHASE6_VALIDATION_EXPORT_NAME}",
        "validation_dates": normalized_dates,
        "row_count": validation_export.height,
        "tick_size": tick_size,
        "sharpe_convention": SHARPE_CONVENTION,
    }
    (validation_dir / PHASE6_VALIDATION_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return trade_log_csv_path, metrics_json_path


def _compute_sharpe_ratio(net_values: list[float]) -> float | None:
    if len(net_values) < 2:
        return None

    mean_value = sum(net_values) / len(net_values)
    squared_diffs = [(value - mean_value) ** 2 for value in net_values]
    sample_variance = sum(squared_diffs) / (len(net_values) - 1)
    sample_std = sqrt(sample_variance)
    if sample_std == 0:
        return None
    return (mean_value / sample_std) * sqrt(len(net_values))


__all__ = [
    "DEFAULT_TICK_SIZE",
    "PHASE5_TRADE_LOG_ARTIFACT_NAME",
    "PHASE6_METRICS_JSON_NAME",
    "PHASE6_TRADE_LOG_CSV_NAME",
    "SHARPE_CONVENTION",
    "compute_performance_metrics",
    "prepare_trade_log",
    "write_core_analytics_artifacts",
]
