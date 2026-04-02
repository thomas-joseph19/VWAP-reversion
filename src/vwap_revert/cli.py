"""Phase 1 command-line entrypoint."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import time

import polars as pl

from .data_pipeline.cache import scan_canonical_cache, write_canonical_cache
from .data_pipeline.contracts import add_contract_trading_date, apply_contract_map, build_daily_contract_map
from .data_pipeline.ingest import collect_sample_day
from .indicators.vwap import attach_daily_vwap_bands, write_enriched_vwap_artifact, write_vwap_validation_export
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
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
