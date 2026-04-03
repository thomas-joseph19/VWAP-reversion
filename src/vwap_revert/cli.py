"""Phase 1 command-line entrypoint."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import time

import polars as pl

from .analytics import write_core_analytics_artifacts
from .data_pipeline.cache import scan_canonical_cache, write_canonical_cache
from .data_pipeline.contracts import add_contract_trading_date, apply_contract_map, build_daily_contract_map
from .data_pipeline.ingest import collect_sample_day
from .indicators.setup_detection import write_setup_detection_artifacts, write_setup_validation_export
from .indicators.structural_levels import (
    attach_prior_day_structural_levels,
    write_structural_levels_artifacts,
    write_structural_validation_export,
)
from .indicators.volume_profile import (
    attach_volume_profile_levels,
    write_volume_profile_artifacts,
    write_volume_profile_validation_export,
)
from .indicators.vwap import attach_daily_vwap_bands, write_enriched_vwap_artifact, write_vwap_validation_export
from .simulation import SimulationConfig, write_trade_simulation_artifacts
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


def _build_normalized_frame(csv_root: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    daily_frames: list[pl.DataFrame] = []
    contract_maps: list[pl.DataFrame] = []

    for entry in build_manifest(csv_root):
        raw_day = collect_sample_day(entry.csv_path)
        contract_map = build_daily_contract_map(raw_day)
        contract_maps.append(contract_map)
        front_month = apply_contract_map(add_contract_trading_date(raw_day), contract_map)
        daily_frames.append(label_sessions(front_month))

    normalized = pl.concat(daily_frames, how="diagonal_relaxed").sort(["trading_date", "ts_recv_et"])
    roll_map = pl.concat(contract_maps, how="diagonal_relaxed").sort("trading_date")
    return normalized, roll_map


def build_phase1_cache(csv_root: Path, output_root: Path, holiday_calendar: Path | None) -> dict:
    """Run the complete phase-1 cache build and artifact emission flow."""

    holidays = _load_holiday_calendar(holiday_calendar)
    output_root.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    normalized, contract_map = _build_normalized_frame(csv_root)
    quality_gaps = detect_intraday_gaps(normalized)
    quality_report = build_quality_report(
        trading_dates=normalized["trading_date"].unique().sort().to_list(),
        expected_dates=[entry.session_date for entry in build_manifest(csv_root)],
        holiday_dates=holidays,
        intraday_gaps=quality_gaps,
        recoverable_row_issues={"dropped_rows": 0},
        examples={"dropped_rows": []},
        contract_map=contract_map,
        session_df=normalized,
    )

    cache_dir = output_root / "canonical_cache"
    write_canonical_cache(normalized, cache_dir)
    contract_map.write_parquet(output_root / "contract_roll_map.parquet")
    (output_root / "schema_summary.json").write_text(
        json.dumps({name: str(dtype) for name, dtype in normalized.schema.items()}, indent=2),
        encoding="utf-8",
    )
    (output_root / "data_quality_report.json").write_text(
        json.dumps(quality_report, indent=2),
        encoding="utf-8",
    )

    first_build_seconds = time.perf_counter() - start
    reload_start = time.perf_counter()
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
    proximity_threshold_points: float = 10.0,
    bucket_size: float = 0.25,
    htf_lookback_sessions: int = 180,
) -> Path:
    """Build deterministic Phase 7 volume-profile artifacts from the canonical cache."""

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_dates = _parse_phase7_validation_dates(validation_dates)
    source_df = scan_canonical_cache(cache_root).collect()
    write_volume_profile_artifacts(
        source_df,
        output_root,
        proximity_threshold_points=proximity_threshold_points,
        bucket_size=bucket_size,
        htf_lookback_sessions=htf_lookback_sessions,
    )
    enriched = pl.read_parquet(output_root / "phase7_volume_profile_enriched.parquet")
    write_volume_profile_validation_export(
        enriched,
        output_root,
        normalized_dates,
        bucket_size=bucket_size,
        htf_lookback_sessions=htf_lookback_sessions,
    )
    return output_root / "phase7_volume_profile_enriched.parquet"


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
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
