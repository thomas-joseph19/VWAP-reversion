"""Phase 8 session-regime indicator helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import polars as pl
from .vwap import attach_daily_vwap_bands


PHASE8_SESSION_REGIMES_ARTIFACT_NAME = "phase8_session_regimes.parquet"
PHASE8_ENRICHED_ARTIFACT_NAME = "phase8_regime_vwap_enriched.parquet"
PHASE8_VALIDATION_EXPORT_NAME = "regime_vwap_validation_export.csv"
PHASE8_VALIDATION_MANIFEST_NAME = "validation_sessions.json"


@dataclass(frozen=True)
class SessionRegimeConfig:
    """Configuration for causal session-regime classification."""
    lookback_sessions: int = 20
    min_history_sessions: int = 20
    threshold_quantile: float = 0.5


def build_session_regimes(
    df: pl.DataFrame,
    config: SessionRegimeConfig = SessionRegimeConfig(),
) -> pl.DataFrame:
    """
    Build a session-level regime table from completed-session volatility.
    
    Returns a DataFrame with one row per trading_date and columns:
    - trading_date
    - session_close_price
    - session_log_return
    - realized_volatility
    - regime_threshold_value
    - regime_label
    - regime_reason
    - history_session_count
    - regime_quality_status
    """
    # 1. Filter to RTH trade rows
    trades = df.filter(pl.col("is_rth") & pl.col("side").is_in(["A", "B"]))
    if trades.is_empty():
        return pl.DataFrame(schema={
            "trading_date": pl.Date,
            "session_close_price": pl.Float64,
            "session_log_return": pl.Float64,
            "realized_volatility": pl.Float64,
            "regime_threshold_value": pl.Float64,
            "regime_label": pl.Utf8,
            "regime_reason": pl.Utf8,
            "history_session_count": pl.UInt32,
            "regime_quality_status": pl.Utf8,
        })

    # 2. Extract session close price (last trade price of each trading_date)
    sessions = (
        trades.sort(["trading_date", "ts_recv"])
        .group_by("trading_date", maintain_order=True)
        .agg(pl.col("price").last().alias("session_close_price"))
    )

    # 3. Compute session log-returns
    sessions = sessions.with_columns(
        pl.col("session_close_price").shift(1).alias("prior_session_close_price")
    ).with_columns(
        (pl.col("session_close_price") / pl.col("prior_session_close_price")).log().alias("session_log_return")
    )

    # 4. Compute realized volatility (rolling std of prior log-returns)
    # The active session T uses returns from sessions < T.
    # So we shift(1) before rolling.
    lookback = config.lookback_sessions
    min_history = config.min_history_sessions
    
    sessions = sessions.with_columns(
        pl.col("session_log_return").shift(1).rolling_std(window_size=lookback, min_samples=1).alias("realized_volatility"),
        pl.int_range(0, pl.len()).alias("history_session_count")
    )

    # 5. Compute rolling median of prior realized volatilities
    sessions = sessions.with_columns(
        pl.col("realized_volatility").shift(1).rolling_median(window_size=lookback, min_samples=1).alias("regime_threshold_value")
    )

    # 6. Apply regime quality status and labels
    sessions = sessions.with_columns(
        pl.when(pl.col("history_session_count") < min_history)
        .then(pl.lit("insufficient_history"))
        .when(pl.col("regime_threshold_value").is_null())
        .then(pl.lit("threshold_unavailable"))
        .otherwise(pl.lit("ok"))
        .alias("regime_quality_status")
    ).with_columns(
        pl.when(pl.col("regime_quality_status") == "ok")
        .then(
            pl.when(pl.col("realized_volatility") >= pl.col("regime_threshold_value"))
            .then(pl.lit("short_gamma"))
            .otherwise(pl.lit("long_gamma"))
        )
        .otherwise(None)
        .alias("regime_label"),
        
        pl.when(pl.col("regime_quality_status") == "ok")
        .then(
            pl.when(pl.col("realized_volatility") >= pl.col("regime_threshold_value"))
            .then(pl.lit("rv_above_threshold"))
            .otherwise(pl.lit("rv_below_threshold"))
        )
        .otherwise(None)
        .alias("regime_reason")
    )

    return sessions.select([
        "trading_date",
        "session_close_price",
        "session_log_return",
        "realized_volatility",
        "regime_threshold_value",
        "regime_label",
        "regime_reason",
        "history_session_count",
        "regime_quality_status"
    ])


def build_roll_bridge_table(df: pl.DataFrame) -> pl.DataFrame:
    """
    Build a list of cumulative roll adjustments for each trading date.
    
    Uses daily_vwap as the reference for roll deltas across symbol changes,
    matching the Phase 7 POC-bridging pattern.
    """
    if "daily_vwap" not in df.columns:
        return pl.DataFrame(schema={"trading_date": pl.Date, "cumulative_roll_shift": pl.Float64})

    # 1. Get one row per trading_date with front_symbol and daily_vwap
    daily = (
        df.group_by("trading_date", maintain_order=True)
        .agg(
            pl.col("front_symbol").last().alias("front_symbol"),
            pl.col("daily_vwap").last().alias("daily_vwap")
        )
        .sort("trading_date")
    )

    # 2. Compute deltas on roll days
    daily = daily.with_columns(
        pl.col("front_symbol").shift(1).alias("prior_symbol"),
        pl.col("daily_vwap").shift(1).alias("prior_vwap")
    ).with_columns(
        pl.when(
            pl.col("front_symbol").is_not_null() & 
            pl.col("prior_symbol").is_not_null() & 
            (pl.col("front_symbol") != pl.col("prior_symbol")) &
            pl.col("daily_vwap").is_not_null() &
            pl.col("prior_vwap").is_not_null()
        )
        .then(pl.col("daily_vwap") - pl.col("prior_vwap"))
        .otherwise(0.0)
        .alias("roll_delta")
    )

    # Note: For bridging an anchor that spans multiple rolls, we need the 
    # cumulative shift from any prior day TO the target day.
    # This is handled during the anchor-specific cumulative math.
    return daily.select("trading_date", "front_symbol", "roll_delta")


def _attach_anchor_ids(df: pl.Expr) -> pl.Expr:
    """Add weekly and monthly anchor IDs derived from ET trading_date (Lazy-compatible)."""
    return df.with_columns(
        pl.struct(
            pl.col("trading_date").dt.iso_year().alias("iso_year"),
            pl.col("trading_date").dt.week().alias("iso_week"),
        ).alias("weekly_anchor_id"),
        pl.col("trading_date").dt.month_start().alias("monthly_anchor_id"),
    )


def extract_session_summaries(cache_root: Path) -> pl.DataFrame:
    """Lazy-scan the cache to extract the close price, VWAP, and sigma for each day."""
    
    # We calculate session-end VWAP and Sigma from raw price/size since Phase 2 might not be cached
    return (
        pl.scan_parquet(cache_root, hive_partitioning=True)
        .filter(pl.col("is_rth") & pl.col("side").is_in(["A", "B"]))
        .group_by("trading_date")
        .agg(
            pl.col("price").last().alias("session_close_price"),
            ((pl.col("price") * pl.col("size")).sum() / pl.col("size").sum()).alias("daily_vwap"),
            (
                ((pl.col("price")**2 * pl.col("size")).sum() / pl.col("size").sum()) - 
                ((pl.col("price") * pl.col("size")).sum() / pl.col("size").sum())**2
            ).clip(lower_bound=0.0).sqrt().alias("daily_sigma"),
            pl.col("front_symbol").last().alias("front_symbol"),
        )
        .collect()
        .sort("trading_date")
    )


def build_session_regimes_from_summaries(
    summaries: pl.DataFrame,
    config: SessionRegimeConfig = SessionRegimeConfig(),
) -> pl.DataFrame:
    """Calculates regimes from pre-extracted session summaries."""
    sessions = summaries.sort("trading_date")

    # Compute session log-returns
    sessions = sessions.with_columns(
        pl.col("session_close_price").shift(1).alias("prior_session_close_price")
    ).with_columns(
        (pl.col("session_close_price") / pl.col("prior_session_close_price")).log().alias("session_log_return")
    )

    # Compute realized volatility
    lookback = config.lookback_sessions
    min_history = config.min_history_sessions
    
    sessions = sessions.with_columns(
        pl.col("session_log_return").shift(1).rolling_std(window_size=lookback, min_samples=1).alias("realized_volatility"),
        pl.int_range(0, pl.len()).alias("history_session_count")
    )

    # Compute threshold
    sessions = sessions.with_columns(
        pl.col("realized_volatility").shift(1).rolling_median(window_size=lookback, min_samples=1).alias("regime_threshold_value")
    )

    # Apply labels
    sessions = sessions.with_columns(
        pl.when(pl.col("history_session_count") < min_history)
        .then(pl.lit("insufficient_history"))
        .when(pl.col("regime_threshold_value").is_null())
        .then(pl.lit("threshold_unavailable"))
        .otherwise(pl.lit("ok"))
        .alias("regime_quality_status")
    ).with_columns(
        pl.when(pl.col("regime_quality_status") == "ok")
        .then(
            pl.when(pl.col("realized_volatility") >= pl.col("regime_threshold_value"))
            .then(pl.lit("short_gamma"))
            .otherwise(pl.lit("long_gamma"))
        )
        .otherwise(None)
        .alias("regime_label"),
        
        pl.when(pl.col("regime_quality_status") == "ok")
        .then(
            pl.when(pl.col("realized_volatility") >= pl.col("regime_threshold_value"))
            .then(pl.lit("rv_above_threshold"))
            .otherwise(pl.lit("rv_below_threshold"))
        )
        .otherwise(None)
        .alias("regime_reason")
    )

    return sessions


def attach_regime_and_multi_timeframe_vwap(
    df: pl.DataFrame,
    config: SessionRegimeConfig = SessionRegimeConfig(),
) -> pl.DataFrame:
    """
    Attach row-level weekly/monthly VWAP and regime classification columns.
    """
    # 1. Gather session-level regime data
    session_regimes = build_session_regimes(df, config)
    
    # 2. Add anchor IDs to full frame
    base = _attach_anchor_ids(df).with_row_index("__row")
    
    # 3. Build roll bridge metadata
    roll_bridge = build_roll_bridge_table(base)
    
    # 4. Filter to eligible RTH trade rows for VWAP calculation
    trades = base.filter(pl.col("is_rth") & pl.col("side").is_in(["A", "B"]))
    
    if trades.is_empty():
        # Join empty or null placeholders and return
        return base.join(session_regimes.select([
            "trading_date", "regime_label", "regime_reason", 
            "regime_quality_status", "regime_threshold_value", "history_session_count"
        ]), on="trading_date", how="left").with_columns(
            pl.lit(None, dtype=pl.Float64).alias("weekly_vwap"),
            pl.lit(None, dtype=pl.Float64).alias("monthly_vwap"),
            pl.lit(None, dtype=pl.Float64).alias("weekly_cum_notional"),
            pl.lit(None, dtype=pl.Float64).alias("weekly_cum_volume"),
            pl.lit(None, dtype=pl.Float64).alias("monthly_cum_notional"),
            pl.lit(None, dtype=pl.Float64).alias("monthly_cum_volume"),
            pl.lit(None, dtype=pl.Float64).alias("regime_min_sigma"),
            pl.lit(None, dtype=pl.Float64).alias("regime_max_sigma"),
            pl.lit(None, dtype=pl.Boolean).alias("regime_extension_passes"),
            pl.lit(False).alias("weekly_roll_adjustment_applied"),
            pl.lit(False).alias("monthly_roll_adjustment_applied"),
            pl.lit(None, dtype=pl.Utf8).alias("weekly_roll_anchor_symbol"),
            pl.lit(None, dtype=pl.Utf8).alias("monthly_roll_anchor_symbol"),
        ).drop("__row").sort("trading_date", "ts_recv")

    # 5. Compute Weekly and Monthly VWAP with roll bridging
    # For each anchor, we need to shift prior prices to the anchor's final symbol axis.
    # Actually, it's easier to shift everything to a common relative axis.
    # But D-08 says "align prior trade prices onto the ACTIVE contract axis".
    # Each row in the anchor has an "active" contract (front_symbol).
    # This is complex because each row's active contract might be different!
    # BUT Phase 7 bridges TO the target session's symbol.
    
    # Let's simplify: compute cumulative roll shift globally first.
    roll_shifts = roll_bridge.with_columns(
        pl.col("roll_delta").cum_sum().alias("cum_roll_shift")
    )
    
    trades = trades.join(roll_shifts.select("trading_date", "cum_roll_shift", "front_symbol"), on="trading_date", how="left")
    
    # adjusted_price = price - cum_roll_shift (this brings everything to an 'origin' symbol)
    # Then for any target row, its price level is origin + target_cum_roll_shift.
    # So vwap_on_target = (cum_notional_on_origin / cum_volume) + target_cum_roll_shift.
    
    trades = trades.with_columns(
        (pl.col("price") - pl.col("cum_roll_shift")).alias("price_origin")
    ).with_columns(
        (pl.col("price_origin") * pl.col("size")).alias("notional_origin")
    )

    # Weekly VWAP
    trades = trades.with_columns(
        pl.col("notional_origin").cum_sum().over("weekly_anchor_id").alias("weekly_cum_notional_origin"),
        pl.col("size").cum_sum().over("weekly_anchor_id").alias("weekly_cum_volume"),
        (pl.col("price") * pl.col("size")).cum_sum().over("weekly_anchor_id").alias("weekly_cum_notional_raw"),
    ).with_columns(
        ((pl.col("weekly_cum_notional_origin") / pl.col("weekly_cum_volume")) + pl.col("cum_roll_shift")).alias("weekly_vwap")
    ).with_columns(
        (pl.col("weekly_vwap") != (pl.col("weekly_cum_notional_raw") / pl.col("weekly_cum_volume"))).alias("weekly_roll_adjustment_applied")
    )
    
    # Monthly VWAP
    trades = trades.with_columns(
        pl.col("notional_origin").cum_sum().over("monthly_anchor_id").alias("monthly_cum_notional_origin"),
        pl.col("size").cum_sum().over("monthly_anchor_id").alias("monthly_cum_volume"),
        (pl.col("price") * pl.col("size")).cum_sum().over("monthly_anchor_id").alias("monthly_cum_notional_raw"),
    ).with_columns(
        ((pl.col("monthly_cum_notional_origin") / pl.col("monthly_cum_volume")) + pl.col("cum_roll_shift")).alias("monthly_vwap")
    ).with_columns(
        (pl.col("monthly_vwap") != (pl.col("monthly_cum_notional_raw") / pl.col("monthly_cum_volume"))).alias("monthly_roll_adjustment_applied")
    )

    # 6. Join back to full frame
    # We need to forward fill VWAP over their respective anchor IDs
    vwap_cols = [
        "weekly_vwap", "monthly_vwap", 
        "weekly_cum_notional_origin", "weekly_cum_volume",
        "monthly_cum_notional_origin", "monthly_cum_volume",
        "weekly_roll_adjustment_applied", "monthly_roll_adjustment_applied",
        "front_symbol" # to use as anchor symbol
    ]
    
    # Prepare indicator frame for join
    indicator_rows = trades.select(["trading_date", "ts_recv", "weekly_anchor_id", "monthly_anchor_id", *vwap_cols])
    
    enriched = (
        base.join(indicator_rows, on=["trading_date", "ts_recv", "weekly_anchor_id", "monthly_anchor_id"], how="left")
        .sort(["trading_date", "ts_recv", "__row"])
    )
    
    # Rename origin columns to final artifact names (weekly_cum_notional, etc.)
    enriched = enriched.rename({
        "weekly_cum_notional_origin": "weekly_cum_notional",
        "monthly_cum_notional_origin": "monthly_cum_notional",
        "front_symbol_right": "roll_anchor_symbol"
    })
    
    # Forward fill
    enriched = enriched.with_columns(
        pl.col("weekly_vwap").forward_fill().over("weekly_anchor_id"),
        pl.col("weekly_cum_notional").forward_fill().over("weekly_anchor_id"),
        pl.col("weekly_cum_volume").forward_fill().over("weekly_anchor_id"),
        pl.col("weekly_roll_adjustment_applied").forward_fill().over("weekly_anchor_id").fill_null(False),
        
        pl.col("monthly_vwap").forward_fill().over("monthly_anchor_id"),
        pl.col("monthly_cum_notional").forward_fill().over("monthly_anchor_id"),
        pl.col("monthly_cum_volume").forward_fill().over("monthly_anchor_id"),
        pl.col("monthly_roll_adjustment_applied").forward_fill().over("monthly_anchor_id").fill_null(False),
        
        pl.col("roll_anchor_symbol").forward_fill().over("weekly_anchor_id").alias("weekly_roll_anchor_symbol"),
        pl.col("roll_anchor_symbol").forward_fill().over("monthly_anchor_id").alias("monthly_roll_anchor_symbol"),
    ).drop("roll_anchor_symbol")

    # 7. Join regime metadata
    enriched = enriched.join(session_regimes.select([
        "trading_date", "regime_label", "regime_reason", 
        "regime_quality_status", "regime_threshold_value", "history_session_count"
    ]), on="trading_date", how="left")
    
    # 8. Apply regime-adjusted sigma expectations per REGM-03
    # short_gamma: min=1.7, max=3.2
    # long_gamma: min=1.5, max=2.4
    enriched = enriched.with_columns(
        pl.when(pl.col("regime_label") == "short_gamma")
        .then(1.7)
        .when(pl.col("regime_label") == "long_gamma")
        .then(1.5)
        .otherwise(None)
        .alias("regime_min_sigma"),
        
        pl.when(pl.col("regime_label") == "short_gamma")
        .then(3.2)
        .when(pl.col("regime_label") == "long_gamma")
        .then(2.4)
        .otherwise(None)
        .alias("regime_max_sigma")
    )
    
    # 9. Compute regime_extension_passes
    # boolean only when price, daily_vwap, daily_sigma, min, max are non-null
    sigma_dist = (pl.col("price") - pl.col("daily_vwap")).abs() / pl.col("daily_sigma")
    enriched = enriched.with_columns(
        pl.when(
            pl.all_horizontal(
                pl.col("price").is_not_null(),
                pl.col("daily_vwap").is_not_null(),
                pl.col("daily_sigma").is_not_null(),
                pl.col("daily_sigma") != 0,
                pl.col("regime_min_sigma").is_not_null(),
                pl.col("regime_max_sigma").is_not_null()
            )
        )
        .then(sigma_dist.is_between(pl.col("regime_min_sigma"), pl.col("regime_max_sigma"), closed="both"))
        .otherwise(None)
        .alias("regime_extension_passes")
    )

    return enriched.sort("__row").drop("__row")


def write_partitioned_regime_vwap_artifacts(
    cache_root: Path,
    output_dir: Path,
    config: SessionRegimeConfig = SessionRegimeConfig(),
) -> tuple[Path, Path]:
    """Memory-efficient partitioned enrichment for Phase 8."""
    output_dir.mkdir(parents=True, exist_ok=True)
    enriched_cache_root = output_dir / "regime_vwap_cache"
    enriched_cache_root.mkdir(parents=True, exist_ok=True)

    # 1. Extract summaries and compute regimes (Tiny memory footprint)
    print("Collecting session summaries for regime calculation...")
    summaries = extract_session_summaries(cache_root)
    session_regimes = build_session_regimes_from_summaries(summaries, config)
    
    # 2. Build roll bridge table
    # Shift daily_vwap to priors
    roll_bridge = summaries.with_columns(
        pl.col("front_symbol").shift(1).alias("prior_symbol"),
        pl.col("daily_vwap").shift(1).alias("prior_vwap")
    ).with_columns(
        pl.when(
            pl.col("front_symbol").is_not_null() & 
            pl.col("prior_symbol").is_not_null() & 
            (pl.col("front_symbol") != pl.col("prior_symbol")) &
            pl.col("daily_vwap").is_not_null() &
            pl.col("prior_vwap").is_not_null()
        )
        .then(pl.col("daily_vwap") - pl.col("prior_vwap"))
        .otherwise(0.0)
        .alias("roll_delta")
    ).with_columns(
        pl.col("roll_delta").cum_sum().alias("cum_roll_shift")
    )

    # 3. Compute Weekly/Monthly VWAP accumulation tables
    # This still requires scanning but we'll do it lazily
    print("Computing Multi-Timeframe VWAP accumulators...")
    full_lazy = pl.scan_parquet(cache_root, hive_partitioning=True)
    full_lazy = full_lazy.filter(pl.col("is_rth") & pl.col("side").is_in(["A", "B"]))
    full_lazy = _attach_anchor_ids(full_lazy)
    
    # Add roll shift to lazy frame for price adjustment
    # We join with our small roll_bridge table
    trades_with_shift = full_lazy.join(roll_bridge.select("trading_date", "cum_roll_shift").lazy(), on="trading_date", how="left")
    
    # Accumulate Weekly
    weekly_acc = (
        trades_with_shift.with_columns(
            ((pl.col("price") - pl.col("cum_roll_shift")) * pl.col("size")).alias("notional_origin")
        )
        .group_by("weekly_anchor_id", "trading_date", "ts_recv")
        .agg(
            pl.col("notional_origin").sum().alias("row_notional_origin"),
            pl.col("size").sum().alias("row_volume"),
        )
        .sort(["weekly_anchor_id", "trading_date", "ts_recv"])
        .with_columns(
            pl.col("row_notional_origin").cum_sum().over("weekly_anchor_id").alias("weekly_cum_notional_origin"),
            pl.col("row_volume").cum_sum().over("weekly_anchor_id").alias("weekly_cum_volume"),
        )
    )

    # Accumulate Monthly
    monthly_acc = (
        trades_with_shift.with_columns(
            ((pl.col("price") - pl.col("cum_roll_shift")) * pl.col("size")).alias("notional_origin")
        )
        .group_by("monthly_anchor_id", "trading_date", "ts_recv")
        .agg(
            pl.col("notional_origin").sum().alias("row_notional_origin_m"),
            pl.col("size").sum().alias("row_volume_m"),
        )
        .sort(["monthly_anchor_id", "trading_date", "ts_recv"])
        .with_columns(
            pl.col("row_notional_origin_m").cum_sum().over("monthly_anchor_id").alias("monthly_cum_notional_origin"),
            pl.col("row_volume_m").cum_sum().over("monthly_anchor_id").alias("monthly_cum_volume"),
        )
    )
    
    print("Materializing HTF accumulators to RAM...")
    weekly_acc_df = weekly_acc.collect()
    monthly_acc_df = monthly_acc.collect()

    # 4. Partitioned Enrichment Loop
    trading_dates = summaries["trading_date"].to_list()
    total_days = len(trading_dates)
    print(f"Enriching {total_days} sessions with regimes and HTF VWAP...")

    for i, t_date in enumerate(trading_dates, 1):
        if i % 20 == 0 or i == 1 or i == total_days:
            print(f"[{i}/{total_days}] Enriching {t_date}...")
            
        day_path = cache_root / f"trading_date={t_date.isoformat()}" / "data.parquet"
        if not day_path.exists():
            continue
            
        day_df = pl.read_parquet(day_path).with_columns(pl.lit(t_date).alias("trading_date"))
        
        # 0. Ensure VWAP/Sigma present
        if "daily_vwap" not in day_df.columns:
            day_df = attach_daily_vwap_bands(day_df)
            
        # 1. Base enrichment
        day_df = _attach_anchor_ids(day_df)
        
        # Join Roll Shift
        shift_val = roll_bridge.filter(pl.col("trading_date") == t_date)["cum_roll_shift"][0]
        
        # Join Weekly/Monthly Acc (Filtering to current day/ts)
        day_weekly = weekly_acc_df.filter(pl.col("trading_date") == t_date)
        day_monthly = monthly_acc_df.filter(pl.col("trading_date") == t_date)
        
        # Join and Compute VWAP
        day_enriched = day_df.join(day_weekly.select("ts_recv", "weekly_cum_notional_origin", "weekly_cum_volume"), on="ts_recv", how="left")
        day_enriched = day_enriched.join(day_monthly.select("ts_recv", "monthly_cum_notional_origin", "monthly_cum_volume"), on="ts_recv", how="left")
        
        day_enriched = day_enriched.with_columns(
            pl.col("weekly_cum_notional_origin").forward_fill(),
            pl.col("weekly_cum_volume").forward_fill(),
            pl.col("monthly_cum_notional_origin").forward_fill(),
            pl.col("monthly_cum_volume").forward_fill(),
        ).with_columns(
            ((pl.col("weekly_cum_notional_origin") / pl.col("weekly_cum_volume")) + shift_val).alias("weekly_vwap"),
            ((pl.col("monthly_cum_notional_origin") / pl.col("monthly_cum_volume")) + shift_val).alias("monthly_vwap"),
        )
        
        # Join Regime
        day_regime = session_regimes.filter(pl.col("trading_date") == t_date)
        day_enriched = day_enriched.join(day_regime.select([
            "trading_date", "regime_label", "regime_reason", 
            "regime_quality_status", "regime_threshold_value", "history_session_count"
        ]), on="trading_date", how="left")
        
        # Apply Sigma Logic
        day_enriched = day_enriched.with_columns(
            pl.when(pl.col("regime_label") == "short_gamma").then(1.7).when(pl.col("regime_label") == "long_gamma").then(1.5).otherwise(None).alias("regime_min_sigma"),
            pl.when(pl.col("regime_label") == "short_gamma").then(3.2).when(pl.col("regime_label") == "long_gamma").then(2.4).otherwise(None).alias("regime_max_sigma")
        )
        
        sigma_dist = (pl.col("price") - pl.col("daily_vwap")).abs() / pl.col("daily_sigma")
        day_enriched = day_enriched.with_columns(
            pl.when(pl.all_horizontal(pl.col("price").is_not_null(), pl.col("daily_vwap").is_not_null(), pl.col("daily_sigma").is_not_null(), pl.col("daily_sigma") != 0, pl.col("regime_min_sigma").is_not_null()))
            .then(sigma_dist.is_between(pl.col("regime_min_sigma"), pl.col("regime_max_sigma"), closed="both"))
            .otherwise(None).alias("regime_extension_passes")
        )
        
        # Write partition
        target_dir = enriched_cache_root / f"trading_date={t_date.isoformat()}"
        target_dir.mkdir(parents=True, exist_ok=True)
        day_enriched.drop("trading_date").write_parquet(target_dir / "data.parquet", compression="zstd")

    session_path = output_dir / PHASE8_SESSION_REGIMES_ARTIFACT_NAME
    session_regimes.write_parquet(session_path)
    
    # Enriched path is now the root of the partitioned dataset
    return session_path, enriched_cache_root


def write_regime_and_multi_timeframe_validation_export(
    enriched_df: pl.DataFrame,
    session_regimes: pl.DataFrame,
    output_dir: Path,
    validation_dates: list[str],
    config: SessionRegimeConfig = SessionRegimeConfig(),
) -> None:
    """Write Phase 8 validation artifacts for selected sessions."""
    val_dir = output_dir / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)
    
    normalized_dates = sorted(dict.fromkeys(validation_dates))
    filtered = enriched_df.filter(pl.col("trading_date").cast(pl.Utf8).is_in(normalized_dates))
    
    csv_path = val_dir / PHASE8_VALIDATION_EXPORT_NAME
    manifest_path = val_dir / PHASE8_VALIDATION_MANIFEST_NAME
    
    # Exact required columns
    val_cols = [
        "trading_date", "ts_recv_et", "weekly_vwap", "monthly_vwap", 
        "regime_label", "regime_reason", "regime_quality_status", 
        "regime_threshold_value", "history_session_count", 
    ]
    filtered.select(val_cols).write_csv(csv_path)
    
    # Exact required manifest keys
    manifest = {
        "validation_dates": normalized_dates,
        "lookback_sessions": config.lookback_sessions,
        "min_history_sessions": config.min_history_sessions,
        "threshold_quantile": config.threshold_quantile,
        "session_regimes_artifact": PHASE8_SESSION_REGIMES_ARTIFACT_NAME,
        "enriched_artifact": PHASE8_ENRICHED_ARTIFACT_NAME,
        "validation_export": f"validation/{PHASE8_VALIDATION_EXPORT_NAME}",
        "row_count": enriched_df.height
    }
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
