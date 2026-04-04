"""Phase 1 command-line entrypoint."""

from __future__ import annotations

import argparse
from datetime import date, time
import json
from pathlib import Path
import time as time_bench

import polars as pl

from .analytics import write_core_analytics_artifacts, compute_performance_metrics
from .data_pipeline.cache import scan_canonical_cache, write_canonical_cache
from .data_pipeline.contracts import add_contract_trading_date, apply_contract_map, build_daily_contract_map
from .data_pipeline.ingest import collect_sample_day
from .indicators.setup_detection import write_setup_detection_artifacts, write_setup_validation_export, attach_setup_detection_features, extract_setup_events
from .indicators.structural_levels import (
    attach_prior_day_structural_levels,
    write_structural_levels_artifacts,
    write_structural_validation_export,
)
from .indicators.volume_profile import (
    write_volume_profile_validation_export,
    write_partitioned_volume_profile_artifacts,
    DEFAULT_BUCKET_SIZE,
    DEFAULT_HTF_LOOKBACK_SESSIONS,
)
from .indicators.regime import (
    SessionRegimeConfig,
    write_regime_and_multi_timeframe_validation_export,
    write_partitioned_regime_vwap_artifacts,
)
from .indicators.vwap import attach_daily_vwap_bands, write_enriched_vwap_artifact, write_vwap_validation_export
from .simulation import SimulationConfig, write_trade_simulation_artifacts, simulate_trades
from .data_pipeline.manifest import build_manifest
from .data_pipeline.quality import build_quality_report, detect_intraday_gaps
from .data_pipeline.sessions import label_sessions


def _load_holiday_calendar(path: Path | None) -> set[date]:
    if path is None:
        return set()

    if path.suffix.lower() == ".json":
        values = json.loads(path.read_text(encoding="utf-8"))
    else:
        values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {date.fromisoformat(value) for value in values}


def _build_cache_and_quality_metadata(
    csv_root: Path, cache_root: Path
) -> tuple[pl.DataFrame, pl.DataFrame, list[date]]:
    contract_maps: list[pl.DataFrame] = []
    intraday_gaps_list: list[pl.DataFrame] = []
    observed_dates: list[date] = []

    manifest = build_manifest(csv_root)
    total = len(manifest)
    print(f"Starting memory-efficient cache migration for {total} files...")

    cache_root.mkdir(parents=True, exist_ok=True)

    for i, entry in enumerate(manifest, 1):
        if i % 10 == 0 or i == 1:
            print(f"[{i}/{total}] Processing {entry.session_date} ({entry.stem})...")
        
        raw_day = collect_sample_day(entry.csv_path)
        if not raw_day.height:
            continue
        
        contract_map = build_daily_contract_map(raw_day)
        if not contract_map.height:
            continue
        contract_maps.append(contract_map)
        
        # Normalize and label sessions
        front_month = apply_contract_map(add_contract_trading_date(raw_day), contract_map)
        session_df = label_sessions(front_month)
        
        if session_df.is_empty():
            continue

        # Collect intraday gaps for this session before discarding from memory
        day_gaps = detect_intraday_gaps(session_df)
        intraday_gaps_list.append(day_gaps)
        
        trading_date = session_df["trading_date"][0]
        observed_dates.append(trading_date)
        
        # Write individual partition to disk
        partition_dir = cache_root / f"trading_date={trading_date.isoformat()}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        session_df.write_parquet(partition_dir / "data.parquet", compression="zstd")

    roll_map = pl.concat(contract_maps, how="diagonal_relaxed").sort("trading_date")
    all_gaps = pl.concat(intraday_gaps_list, how="diagonal_relaxed") if intraday_gaps_list else detect_intraday_gaps(pl.DataFrame())
    
    return roll_map, all_gaps, sorted(observed_dates)


def build_phase1_cache(csv_root: Path, output_root: Path, holiday_calendar: Path | None) -> dict:
    """Run the complete phase-1 cache build and artifact emission flow."""

    holidays = _load_holiday_calendar(holiday_calendar)
    output_root.mkdir(parents=True, exist_ok=True)
    cache_dir = output_root / "canonical_cache"

    start = time.perf_counter()
    contract_map, quality_gaps, observed_dates = _build_cache_and_quality_metadata(csv_root, cache_dir)
    
    quality_report = build_quality_report(
        trading_dates=observed_dates,
        expected_dates=[entry.session_date for entry in build_manifest(csv_root)],
        holiday_dates=holidays,
        intraday_gaps=quality_gaps,
        recoverable_row_issues={"dropped_rows": 0},
        examples={"dropped_rows": []},
        contract_map=contract_map,
        session_df=None,  # We skip session_df check here as we already validated per-day
    )

    contract_map.write_parquet(output_root / "contract_roll_map.parquet")
    
    # Peek at first partition for schema summary
    first_date = str(observed_dates[0]) if observed_dates else "unknown"
    sample_df = pl.read_parquet(cache_dir / f"trading_date={first_date}" / "data.parquet")
    (output_root / "schema_summary.json").write_text(
        json.dumps({name: str(dtype) for name, dtype in sample_df.schema.items()}, indent=2),
        encoding="utf-8",
    )
    
    (output_root / "data_quality_report.json").write_text(
        json.dumps(quality_report, indent=2),
        encoding="utf-8",
    )

    start = time_bench.perf_counter()
    contract_map, quality_gaps, observed_dates = _build_cache_and_quality_metadata(csv_root, cache_dir)
    
    quality_report = build_quality_report(
        trading_dates=observed_dates,
        expected_dates=[entry.session_date for entry in build_manifest(csv_root)],
        holiday_dates=holidays,
        intraday_gaps=quality_gaps,
        recoverable_row_issues={"dropped_rows": 0},
        examples={"dropped_rows": []},
        contract_map=contract_map,
        session_df=None,  # We skip session_df check here as we already validated per-day
    )

    contract_map.write_parquet(output_root / "contract_roll_map.parquet")
    
    # Peek at first partition for schema summary
    first_date = str(observed_dates[0]) if observed_dates else "unknown"
    sample_df = pl.read_parquet(cache_dir / f"trading_date={first_date}" / "data.parquet")
    (output_root / "schema_summary.json").write_text(
        json.dumps({name: str(dtype) for name, dtype in sample_df.schema.items()}, indent=2),
        encoding="utf-8",
    )
    
    (output_root / "data_quality_report.json").write_text(
        json.dumps(quality_report, indent=2),
        encoding="utf-8",
    )

    first_build_seconds = time_bench.perf_counter() - start
    reload_start = time_bench.perf_counter()
    scan_canonical_cache(cache_dir).collect()
    cache_reload_seconds = time.perf_counter() - reload_start

    benchmark = {
        "first_build_seconds": round(first_build_seconds, 6),
        "cache_reload_seconds": round(cache_reload_seconds, 6),
        "reload_under_30_seconds": cache_reload_seconds < 30.0,
    }
    (output_root / "cache_benchmark.json").write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    return benchmark


def _parse_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if len(normalized) < 5:
        raise ValueError("build-phase2-vwap requires at least five --validation-date values for manual validation")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def build_phase2_vwap(cache_root: Path, output_root: Path, validation_dates: list[str]) -> Path:
    """Build the reusable phase-2 indicator artifact and validation export."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_validation_dates(validation_dates)
    enriched = attach_daily_vwap_bands(scan_canonical_cache(cache_root).collect())
    write_enriched_vwap_artifact(enriched, output_root)
    write_vwap_validation_export(enriched, output_root, normalized_dates)
    return output_root / "phase2_daily_vwap.parquet"


def _parse_phase3_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if not normalized:
        raise ValueError("build-phase3-structural-levels requires at least one --validation-date value")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def build_phase3_structural_levels(
    cache_root: Path,
    output_root: Path,
    validation_dates: list[str],
    proximity_threshold_points: float = 10.0,
) -> Path:
    """Build the reusable phase-3 structural artifacts and validation export."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase3_validation_dates(validation_dates)
    source_df = scan_canonical_cache(cache_root).collect()
    _, enriched_path = write_structural_levels_artifacts(
        source_df,
        output_root,
        proximity_threshold_points=proximity_threshold_points,
    )
    write_structural_validation_export(pl.read_parquet(enriched_path), output_root, normalized_dates)
    return output_root / "phase3_structural_enriched.parquet"


def _parse_phase4_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if not normalized:
        raise ValueError("build-phase4-setup-detection requires at least one --validation-date value")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def build_phase4_setup_detection(
    cache_root: Path,
    output_root: Path,
    validation_dates: list[str],
    proximity_threshold_points: float = 10.0,
    min_sigma: float = 1.7,
    max_sigma: float = 3.0,
) -> Path:
    """Build the reusable phase-4 setup-detection artifacts and validation export."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase4_validation_dates(validation_dates)
    source_df = scan_canonical_cache(cache_root).collect()
    vwap_enriched = attach_daily_vwap_bands(source_df)
    structural_enriched = attach_prior_day_structural_levels(
        vwap_enriched,
        proximity_threshold_points=proximity_threshold_points,
    )
    enriched_path, _ = write_setup_detection_artifacts(
        structural_enriched,
        output_root,
        min_sigma=min_sigma,
        max_sigma=max_sigma,
    )
    write_setup_validation_export(pl.read_parquet(enriched_path), output_root, normalized_dates)
    return output_root / "phase4_setup_log.parquet"


def _parse_phase5_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if not normalized:
        raise ValueError("build-phase5-trade-simulation requires at least one --validation-date value")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def build_phase5_trade_simulation(
    phase4_root: Path,
    output_root: Path,
    validation_dates: list[str],
    stop_loss_points: float = 20.0,
    round_trip_commission: float = 5.0,
    additional_slippage_points: float = 0.0,
) -> Path:
    """Build deterministic Phase 5 trade artifacts from Phase 4 outputs."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase5_validation_dates(validation_dates)
    config = SimulationConfig(
        stop_loss_points=stop_loss_points,
        round_trip_commission=round_trip_commission,
        additional_slippage_points=additional_slippage_points,
    )
    trade_log_path, _ = write_trade_simulation_artifacts(
        phase4_root=phase4_root,
        output_root=output_root,
        validation_dates=normalized_dates,
        config=config,
    )
    return trade_log_path


def _parse_phase6_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if not normalized:
        raise ValueError("build-phase6-core-analytics requires at least one --validation-date value")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def build_phase6_core_analytics(phase5_root: Path, output_root: Path, validation_dates: list[str]) -> Path:
    """Build deterministic Phase 6 analytics artifacts from Phase 5 outputs."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase6_validation_dates(validation_dates)
    trade_log_csv_path, _ = write_core_analytics_artifacts(
        phase5_root=phase5_root,
        output_root=output_root,
        validation_dates=normalized_dates,
    )
    return trade_log_csv_path


def _parse_phase7_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if not normalized:
        raise ValueError("build-phase7-volume-profile requires at least one --validation-date value")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def build_phase7_volume_profile(
    cache_root: Path,
    output_root: Path,
    validation_dates: list[str],
    bucket_size: float = DEFAULT_BUCKET_SIZE,
    htf_lookback_sessions: int = DEFAULT_HTF_LOOKBACK_SESSIONS,
    proximity_threshold_points: float = 10.0,
    force_rebuild: bool = False,
) -> Path:
    """Build Phase 7 volume profile artifacts from the canonical cache."""
    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase7_validation_dates(validation_dates)
    
    enriched_cache_root = output_root / "volume_profiles" / "volume_profile_cache"
    if enriched_cache_root.exists() and not force_rebuild:
        print("Using existing Phase 7 partitioned cache...")
        return enriched_cache_root

    # Build partitioned artifacts
    _, _, _, enriched_cache_root = write_partitioned_volume_profile_artifacts(
        cache_root,
        output_root / "volume_profiles",
        proximity_threshold_points=proximity_threshold_points,
        bucket_size=bucket_size,
        htf_lookback_sessions=htf_lookback_sessions,
    )
    
    # Validation uses partitioned scan to include trading_date
    val_df = pl.scan_parquet(enriched_cache_root, hive_partitioning=True).filter(
        pl.col("trading_date").cast(pl.Utf8).is_in(normalized_dates)
    ).collect()
    
    write_volume_profile_validation_export(
        val_df,
        output_root,
        normalized_dates,
        bucket_size=bucket_size,
        htf_lookback_sessions=htf_lookback_sessions,
    )
    
    return enriched_cache_root


def _parse_phase8_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if not normalized:
        raise ValueError("build-phase8-regime-vwap requires at least one --validation-date value")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def build_phase8_regime_vwap(
    cache_root: Path,
    output_root: Path,
    validation_dates: list[str],
    lookback_sessions: int = 20,
    min_history_sessions: int = 20,
    threshold_quantile: float = 0.5,
    force_rebuild: bool = False,
) -> Path:
    """Build deterministic Phase 8 regime and multi-timeframe VWAP artifacts from the canonical cache."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase8_validation_dates(validation_dates)
    
    enriched_cache_path = output_root / "regime_indicators" / "regime_vwap_cache"
    if enriched_cache_path.exists() and not force_rebuild:
        print("Using existing Phase 8 partitioned cache...")
        return enriched_cache_path

    config = SessionRegimeConfig(
        lookback_sessions=lookback_sessions,
        min_history_sessions=min_history_sessions,
        threshold_quantile=threshold_quantile,
    )
    
    # Use partitioned version for memory efficiency
    sess_path, enriched_cache_path = write_partitioned_regime_vwap_artifacts(
        cache_root,
        output_root,
        config=config,
    )
    
    # Validation uses partitioned scan to include trading_date
    val_df = pl.scan_parquet(enriched_cache_path, hive_partitioning=True).filter(
        pl.col("trading_date").cast(pl.Utf8).is_in(normalized_dates)
    ).collect()

    write_regime_and_multi_timeframe_validation_export(
        enriched_df=val_df,
        session_regimes=pl.read_parquet(sess_path),
        output_dir=output_root,
        validation_dates=normalized_dates,
        config=config,
    )
    
    return enriched_cache_path


def _parse_phase9_validation_dates(validation_dates: list[str]) -> list[str]:
    normalized = sorted(dict.fromkeys(validation_dates))
    if not normalized:
        raise ValueError("build-phase9-integration requires at least one --validation-date value")

    for value in normalized:
        date.fromisoformat(value)
    return normalized


def str2bool(v: str) -> bool:
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def build_phase9_integration(
    cache_root: Path,
    output_root: Path,
    validation_dates: list[str],
    proximity_threshold_points: float = 10.0,
    min_sigma: float = 1.7,
    max_sigma: float = 4.5,
    t1_target_multiple: float = 0.5,
    max_hold_seconds: int = 3600,
    stop_loss_points: float = 20.0,
    stop_loss_multiple: float = 1.0,
    round_trip_commission: float = 5.0,
    additional_slippage_points: float = 0.0,
    units: int = 2,
    break_even_on_t1: bool = True,
    skip_confluence: bool = False,
    profit_target_multiple: float = 1.0,
) -> Path:
    """Build the full Phase 9 backtest artifacts integrating all prior indicators."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase9_validation_dates(validation_dates)
    
    # 1. Build Indicator Caches (Partitioned)
    print("--- Phase 1. Build Indicator Caches (Partitioned) ---")
    profile_output = output_root / "volume_profiles"
    regime_output = output_root / "regime_indicators"
    
    profile_cache_root = build_phase7_volume_profile(
        cache_root, 
        profile_output, 
        normalized_dates,
        proximity_threshold_points=proximity_threshold_points,
        force_rebuild=False
    )
    regime_cache_root = build_phase8_regime_vwap(
        cache_root, 
        regime_output, 
        normalized_dates, 
        force_rebuild=False
    )
    
    # 3. Integrate and Run Simulation (Day-by-Day)
    print("--- Phase 9: Setup Detection & Simulation (Day-by-Day) ---")
    sim_output = output_root / "simulation"
    sim_output.mkdir(parents=True, exist_ok=True)
    
    # Discovery from regime cache
    trading_dates = sorted([date.fromisoformat(p.name.split("=")[1]) for p in regime_cache_root.glob("trading_date=*")])
    total_days = len(trading_dates)
    
    all_setup_logs: list[pl.DataFrame] = []
    simulation_logs: list[pl.DataFrame] = []
    
    # Setup Detection Config (hardcoded window for now)
    window_start = time(9, 30)
    window_end = time(11, 30)

    for i, t_date in enumerate(trading_dates, 1):
        if i % 20 == 0 or i == 1 or i == total_days:
            print(f"[{i}/{total_days}] Simulating {t_date}...")
            
        regime_path = regime_cache_root / f"trading_date={t_date.isoformat()}" / "data.parquet"
        profile_path = profile_cache_root / f"trading_date={t_date.isoformat()}" / "data.parquet"
        
        if not (regime_path.exists() and profile_path.exists()):
            continue
            
        regime_df = pl.read_parquet(regime_path).with_columns(pl.lit(t_date).alias("trading_date"))
        profile_df = pl.read_parquet(profile_path).with_columns(pl.lit(t_date).alias("trading_date"))
        
        # 0. Ensure VWAP and Sigma are present (if loading from Phase 1 partitions)
        if "daily_vwap" not in regime_df.columns:
            # Note: attach_daily_vwap_bands will use raw price/size columns in regime_df
            regime_df = attach_daily_vwap_bands(regime_df)
            
        # Merge structural levels into regime base
        struc_cols = [c for c in profile_df.columns if "structural" in c or "distance_to" in c or "prior_rth" in c or "overnight_" in c or "htf_" in c]
        struc_cols.append("ts_recv")
        
        integrated = regime_df.join(profile_df.select(struc_cols), on="ts_recv", how="left")
        
        # Run Detection
        final_enriched = attach_setup_detection_features(
            integrated,
            window_start=window_start,
            window_end=window_end,
            min_sigma=min_sigma,
            max_sigma=max_sigma,
        )
        
        # Override Confluence if requested
        if skip_confluence:
            final_enriched = final_enriched.with_columns(
                pl.lit(True).alias("structural_confluence_passes")
            )
        
        # Funnel Summary (Debug)
        if i % 100 == 0 or i == 1:
            win_pass = final_enriched.select(pl.col("time_window_passes").sum()).item()
            ext_pass = final_enriched.select(pl.col("vwap_extension_passes").sum()).item()
            struc_pass = final_enriched.select(pl.col("structural_confluence_passes").sum()).item()
            ev_pass = final_enriched.select(pl.col("setup_event_emitted").sum()).item()
            print(f"--- Funnel {t_date} --- RTH: {len(final_enriched)} | Win: {win_pass} | Ext: {ext_pass} | Struct: {struc_pass} | Ev: {ev_pass}")
            
        # Extraction
        day_setup_log = extract_setup_events(final_enriched).with_columns(
            pl.col("regime_label").forward_fill(),
            pl.col("regime_reason").forward_fill(),
        )
        if day_setup_log.height > 0:
            all_setup_logs.append(day_setup_log)
            
            # Simulation
            sim_config = SimulationConfig(
                stop_loss_points=stop_loss_points,
                round_trip_commission=round_trip_commission,
                additional_slippage_points=additional_slippage_points,
                units=units,
                break_even_on_t1=break_even_on_t1,
                profit_target_multiple=profit_target_multiple,
                t1_profit_target_multiple=t1_target_multiple,
                max_hold_seconds=max_hold_seconds,
                stop_loss_multiple=stop_loss_multiple,
            )
            batch_result = simulate_trades(
                day_setup_log,
                final_enriched,
                config=sim_config
            )
            if batch_result.trade_log.height > 0:
                simulation_logs.append(batch_result.trade_log)

    # 4. Final Aggregation
    analytics_output = output_root / "analytics"
    analytics_output.mkdir(parents=True, exist_ok=True)

    if all_setup_logs:
        full_setup_log = pl.concat(all_setup_logs, how="diagonal_relaxed")
        full_setup_log.write_parquet(sim_output / "phase9_setup_log.parquet")
    
    if simulation_logs:
        full_sim_log = pl.concat(simulation_logs, how="diagonal_relaxed")
        full_sim_log.write_parquet(sim_output / "phase9_simulation_log.parquet")
        
        # Note: we need 'net_dollars' for compute_performance_metrics.
        # Ensure it exists in simulation log.
        summary = compute_performance_metrics(full_sim_log)
        (analytics_output / "phase9_performance_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(f"Backtest Complete! Trade Count: {summary.get('trade_count', 0)}")
    else:
        print("Backtest Complete - No trades generated.")

    return analytics_output / "phase9_performance_summary.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vwap_revert")
    subparsers = parser.add_subparsers(dest="command", required=True)

    phase1 = subparsers.add_parser("build-phase1-cache")
    phase1.add_argument("--csv-root", type=Path, required=True)
    phase1.add_argument("--output-root", type=Path, required=True)
    phase1.add_argument("--holiday-calendar", type=Path)

    phase2 = subparsers.add_parser("build-phase2-vwap")
    phase2.add_argument("--cache-root", type=Path, required=True)
    phase2.add_argument("--output-root", type=Path, required=True)
    phase2.add_argument("--validation-date", dest="validation_dates", action="append", required=True)

    phase3 = subparsers.add_parser("build-phase3-structural-levels")
    phase3.add_argument("--cache-root", type=Path, required=True)
    phase3.add_argument("--output-root", type=Path, required=True)
    phase3.add_argument("--validation-date", dest="validation_dates", action="append", required=True)
    phase3.add_argument("--proximity-threshold-points", type=float, default=10.0)

    phase4 = subparsers.add_parser("build-phase4-setup-detection")
    phase4.add_argument("--cache-root", type=Path, required=True)
    phase4.add_argument("--output-root", type=Path, required=True)
    phase4.add_argument("--validation-date", dest="validation_dates", action="append", required=True)
    phase4.add_argument("--proximity-threshold-points", type=float, default=10.0)
    phase4.add_argument("--min-sigma", type=float, default=1.7)
    phase4.add_argument("--max-sigma", type=float, default=3.0)

    phase5 = subparsers.add_parser("build-phase5-trade-simulation")
    phase5.add_argument("--phase4-root", type=Path, required=True)
    phase5.add_argument("--output-root", type=Path, required=True)
    phase5.add_argument("--validation-date", dest="validation_dates", action="append", required=True)
    phase5.add_argument("--stop-loss-points", type=float, default=20.0)
    phase5.add_argument("--round-trip-commission", type=float, default=5.0)
    phase5.add_argument("--additional-slippage-points", type=float, default=0.0)

    phase6 = subparsers.add_parser("build-phase6-core-analytics")
    phase6.add_argument("--phase5-root", type=Path, required=True)
    phase6.add_argument("--output-root", type=Path, required=True)
    phase6.add_argument("--validation-date", dest="validation_dates", action="append", required=True)

    phase7 = subparsers.add_parser("build-phase7-volume-profile")
    phase7.add_argument("--cache-root", type=Path, required=True)
    phase7.add_argument("--output-root", type=Path, required=True)
    phase7.add_argument("--validation-date", dest="validation_dates", action="append", required=True)
    phase7.add_argument("--proximity-threshold-points", type=float, default=10.0)
    phase7.add_argument("--bucket-size", type=float, default=0.25)
    phase7.add_argument("--htf-lookback-sessions", type=int, default=180)

    phase8 = subparsers.add_parser("build-phase8-regime-vwap")
    phase8.add_argument("--cache-root", type=Path, required=True)
    phase8.add_argument("--output-root", type=Path, required=True)
    phase8.add_argument("--validation-date", dest="validation_dates", action="append", required=True)
    phase8.add_argument("--lookback-sessions", type=int, default=20)
    phase8.add_argument("--min-history-sessions", type=int, default=20)
    phase8.add_argument("--threshold-quantile", type=float, default=0.5)

    phase9 = subparsers.add_parser("build-phase9-integration")
    phase9.add_argument("--cache-root", type=Path, required=True)
    phase9.add_argument("--output-root", type=Path, required=True)
    phase9.add_argument("--validation-date", dest="validation_dates", action="append", required=True)
    phase9.add_argument("--proximity-threshold-points", type=float, default=10.0)
    phase9.add_argument("--min-sigma", "--min_sigma", type=float, default=1.7)
    phase9.add_argument("--max-sigma", "--max_sigma", type=float, default=3.0)
    phase9.add_argument("--t1-target-multiple", "--t1_target_multiple", type=float, default=0.5)
    phase9.add_argument("--max-hold-seconds", "--max_hold_seconds", type=int, default=3600)
    phase9.add_argument("--stop-loss-points", "--stop_loss_points", type=float, default=20.0)
    phase9.add_argument("--round-trip-commission", type=float, default=5.0)
    phase9.add_argument("--additional-slippage-points", type=float, default=0.0)
    phase9.add_argument("--units", type=int, default=2)
    phase9.add_argument("--break-even-on-t1", "--break_even_on_t1", type=str2bool, default=True)
    phase9.add_argument("--skip-confluence", "--skip_confluence", type=str2bool, default=False)
    phase9.add_argument("--profit-target-multiple", "--profit_target_multiple", type=float, default=1.0)
    phase9.add_argument("--stop-loss-multiple", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build-phase1-cache":
        build_phase1_cache(args.csv_root, args.output_root, args.holiday_calendar)
        return 0
    if args.command == "build-phase2-vwap":
        build_phase2_vwap(args.cache_root, args.output_root, args.validation_dates)
        return 0
    if args.command == "build-phase3-structural-levels":
        build_phase3_structural_levels(
            args.cache_root,
            args.output_root,
            args.validation_dates,
            proximity_threshold_points=args.proximity_threshold_points,
        )
        return 0
    if args.command == "build-phase4-setup-detection":
        build_phase4_setup_detection(
            args.cache_root,
            args.output_root,
            args.validation_dates,
            proximity_threshold_points=args.proximity_threshold_points,
            min_sigma=args.min_sigma,
            max_sigma=args.max_sigma,
        )
        return 0
    if args.command == "build-phase5-trade-simulation":
        build_phase5_trade_simulation(
            args.phase4_root,
            args.output_root,
            args.validation_dates,
            stop_loss_points=args.stop_loss_points,
            round_trip_commission=args.round_trip_commission,
            additional_slippage_points=args.additional_slippage_points,
        )
        return 0
    if args.command == "build-phase6-core-analytics":
        build_phase6_core_analytics(
            args.phase5_root,
            args.output_root,
            args.validation_dates,
        )
        return 0
    if args.command == "build-phase7-volume-profile":
        build_phase7_volume_profile(
            args.cache_root,
            args.output_root,
            args.validation_dates,
            proximity_threshold_points=args.proximity_threshold_points,
            bucket_size=args.bucket_size,
            htf_lookback_sessions=args.htf_lookback_sessions,
        )
        return 0
    if args.command == "build-phase8-regime-vwap":
        build_phase8_regime_vwap(
            cache_root=args.cache_root,
            output_root=args.output_root,
            validation_dates=args.validation_dates,
            lookback_sessions=args.lookback_sessions,
            min_history_sessions=args.min_history_sessions,
            threshold_quantile=args.threshold_quantile,
        )
        return 0
    if args.command == "build-phase9-integration":
        build_phase9_integration(
            cache_root=args.cache_root,
            output_root=args.output_root,
            validation_dates=args.validation_dates,
            proximity_threshold_points=args.proximity_threshold_points,
            min_sigma=args.min_sigma,
            max_sigma=args.max_sigma,
            t1_target_multiple=args.t1_target_multiple,
            max_hold_seconds=args.max_hold_seconds,
            stop_loss_points=args.stop_loss_points,
            round_trip_commission=args.round_trip_commission,
            additional_slippage_points=args.additional_slippage_points,
            units=args.units,
            break_even_on_t1=args.break_even_on_t1,
            skip_confluence=args.skip_confluence,
            profit_target_multiple=args.profit_target_multiple,
            stop_loss_multiple=args.stop_loss_multiple,
        )
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
