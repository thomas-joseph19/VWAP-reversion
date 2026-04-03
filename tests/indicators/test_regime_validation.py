from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import polars as pl
import pytest

from vwap_revert.cli import main
from vwap_revert.data_pipeline.cache import write_canonical_cache

VALIDATION_COLUMNS = [
    "trading_date",
    "ts_recv_et",
    "weekly_vwap",
    "monthly_vwap",
    "regime_label",
    "regime_reason",
    "regime_quality_status",
    "regime_threshold_value",
    "history_session_count",
    "weekly_roll_adjustment_applied",
    "monthly_roll_adjustment_applied",
]

SESSION_COLUMNS = [
    "session_close_price",
    "session_log_return",
    "realized_volatility",
    "regime_threshold_value",
    "regime_label",
    "regime_reason",
    "history_session_count",
    "regime_quality_status",
]

def _ts(y: int, m: int, d: int, h: int, mn: int, s: int = 0) -> datetime:
    return datetime(y, m, d, h, mn, s, tzinfo=UTC)

def _fixture_frame() -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    # 25 days to clear the 20-session lookback
    start = date(2025, 1, 1)
    for i in range(25):
        tr_date = start + timedelta(days=i)
        # Add 3 trades per day
        for j in range(3):
            ts = _ts(tr_date.year, tr_date.month, tr_date.day, 14, 30, j)
            ts_et = ts - timedelta(hours=5) # simple ET offset
            price = 15000.0 + i + j
            rows.append({
                "trading_date": tr_date,
                "ts_recv": ts,
                "ts_recv_et": ts_et,
                "is_overnight": False,
                "is_rth": True,
                "side": "A" if j % 2 == 0 else "B",
                "price": price,
                "size": 1.0,
                "front_symbol": "NQH5",
                "daily_vwap": price - 1.0,
                "daily_sigma": 5.0,
            })
    return pl.DataFrame(rows)

def _make_temp_dir() -> Path:
    root = Path(".codex_tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    return path

def test_cli_writes_phase8_regime_and_multi_timeframe_vwap_artifacts() -> None:
    tmp_path = _make_temp_dir()
    cache_root = tmp_path / "canonical_cache"
    output_root = tmp_path / "phase8_output"
    try:
        write_canonical_cache(_fixture_frame(), cache_root)
        
        # Exact command from requirements
        exit_code = main([
            "build-phase8-regime-vwap",
            "--cache-root", str(cache_root),
            "--output-root", str(output_root),
            "--validation-date", "2025-01-20",
            "--validation-date", "2025-01-21",
            "--lookback-sessions", "20",
            "--min-history-sessions", "20",
            "--threshold-quantile", "0.5"
        ])
        
        assert exit_code == 0
        
        # Files should exist
        session_parquet = output_root / "phase8_session_regimes.parquet"
        enriched_parquet = output_root / "phase8_regime_vwap_enriched.parquet"
        validation_csv = output_root / "validation" / "regime_vwap_validation_export.csv"
        manifest_json = output_root / "validation" / "validation_sessions.json"
        
        assert session_parquet.exists()
        assert enriched_parquet.exists()
        assert validation_csv.exists()
        assert manifest_json.exists()
        
        # Validate CSV columns
        val_df = pl.read_csv(validation_csv, try_parse_dates=True)
        for col in VALIDATION_COLUMNS:
            assert col in val_df.columns
            
        # Validate session parquet columns
        sess_df = pl.read_parquet(session_parquet)
        for col in SESSION_COLUMNS:
            assert col in sess_df.columns
            
        # Validate manifest
        with open(manifest_json, "r") as f:
            manifest = json.load(f)
            
        assert manifest["validation_dates"] == ["2025-01-20", "2025-01-21"]
        assert manifest["lookback_sessions"] == 20
        assert manifest["min_history_sessions"] == 20
        assert manifest["threshold_quantile"] == 0.5
        assert manifest["session_regimes_artifact"] == "phase8_session_regimes.parquet"
        assert manifest["enriched_artifact"] == "phase8_regime_vwap_enriched.parquet"
        assert manifest["validation_export"] == "validation/regime_vwap_validation_export.csv"
        assert "row_count" in manifest
        
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
