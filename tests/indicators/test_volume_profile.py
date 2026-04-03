from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl

from vwap_revert.indicators.volume_profile import (
    attach_volume_profile_levels,
    build_daily_rth_profiles,
    build_htf_profiles,
    build_overnight_profiles,
    detect_lvn_prices,
)


def _ts(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _session_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                date(2023, 6, 14),
                date(2023, 6, 14),
                date(2023, 6, 14),
                date(2023, 6, 14),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 16),
                date(2023, 6, 16),
                date(2023, 6, 16),
            ],
            "ts_recv": [
                _ts(2023, 6, 14, 13, 30),
                _ts(2023, 6, 14, 13, 31),
                _ts(2023, 6, 14, 13, 32),
                _ts(2023, 6, 14, 13, 33),
                _ts(2023, 6, 14, 23, 0),
                _ts(2023, 6, 15, 0, 0),
                _ts(2023, 6, 15, 12, 0),
                _ts(2023, 6, 15, 13, 30),
                _ts(2023, 6, 15, 13, 31),
                _ts(2023, 6, 15, 13, 32),
                _ts(2023, 6, 15, 15, 0),
                _ts(2023, 6, 16, 13, 30),
                _ts(2023, 6, 16, 13, 31),
                _ts(2023, 6, 16, 13, 32),
            ],
            "ts_recv_et": [
                _ts(2023, 6, 14, 13, 30),
                _ts(2023, 6, 14, 13, 31),
                _ts(2023, 6, 14, 13, 32),
                _ts(2023, 6, 14, 13, 33),
                _ts(2023, 6, 14, 23, 0),
                _ts(2023, 6, 15, 0, 0),
                _ts(2023, 6, 15, 12, 0),
                _ts(2023, 6, 15, 13, 30),
                _ts(2023, 6, 15, 13, 31),
                _ts(2023, 6, 15, 13, 32),
                _ts(2023, 6, 15, 15, 0),
                _ts(2023, 6, 16, 13, 30),
                _ts(2023, 6, 16, 13, 31),
                _ts(2023, 6, 16, 13, 32),
            ],
            "is_overnight": [
                False,
                False,
                False,
                False,
                True,
                True,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
            ],
            "is_rth": [
                True,
                True,
                True,
                True,
                False,
                False,
                False,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
            ],
            "side": [
                "A",
                "B",
                "A",
                "N",
                "A",
                "B",
                "A",
                "A",
                "B",
                "A",
                "N",
                "B",
                "A",
                "B",
            ],
            "price": [
                100.00,
                100.25,
                100.50,
                100.75,
                101.01,
                100.74,
                103.00,
                102.01,
                102.24,
                102.51,
                101.75,
                103.00,
                103.24,
                103.51,
            ],
            "size": [
                10.0,
                30.0,
                20.0,
                999.0,
                15.0,
                5.0,
                500.0,
                10.0,
                15.0,
                20.0,
                600.0,
                5.0,
                8.0,
                13.0,
            ],
            "front_symbol": ["NQU3"] * 14,
        },
        strict=False,
    )


def _htf_fixture(days: int = 3) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for offset in range(days):
        trading_day = date(2023, 6, 14 + offset)
        base_price = 100.0 + offset
        for minute, price, size in (
            (30, base_price, 10.0 + offset),
            (31, base_price + 0.25, 20.0 + offset),
            (32, base_price + 0.50, 15.0 + offset),
        ):
            rows.append(
                {
                    "trading_date": trading_day,
                    "ts_recv": _ts(2023, 6, 14 + offset, 13, minute),
                    "ts_recv_et": _ts(2023, 6, 14 + offset, 13, minute),
                    "is_overnight": False,
                    "is_rth": True,
                    "side": "A" if minute != 31 else "B",
                    "price": price,
                    "size": size,
                    "front_symbol": "NQU3",
                }
            )
    return pl.DataFrame(rows, strict=False)


def _mixed_roll_daily_profiles() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [date(2023, 9, 18), date(2023, 9, 19), date(2023, 9, 20)],
            "profile_family": ["daily_rth", "daily_rth", "daily_rth"],
            "source_trading_date": [date(2023, 9, 18), date(2023, 9, 19), date(2023, 9, 20)],
            "bucket_size": [0.25, 0.25, 0.25],
            "bucket_prices": [[15000.0, 15000.25], [15100.0, 15100.25], [15150.0, 15150.25]],
            "bucket_volumes": [[10.0, 20.0], [12.0, 18.0], [14.0, 16.0]],
            "daily_rth_poc": [15000.25, 15100.25, 15150.25],
            "daily_rth_vah": [15000.25, 15100.25, 15150.25],
            "daily_rth_val": [15000.0, 15100.0, 15150.0],
            "prior_rth_poc": [None, 15000.25, 15100.25],
            "prior_rth_vah": [None, 15000.25, 15100.25],
            "prior_rth_val": [None, 15000.0, 15100.0],
            "lvn_prices": [[], [], []],
            "profile_trade_rows": [2, 2, 2],
            "profile_total_volume": [30.0, 30.0, 30.0],
            "quality_status": ["ok", "ok", "ok"],
            "front_symbol": ["NQU3", "NQZ3", "NQZ3"],
        },
        strict=False,
    )


def _phase7_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                date(2023, 6, 14),
                date(2023, 6, 14),
                date(2023, 6, 14),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 15),
                date(2023, 6, 16),
                date(2023, 6, 16),
                date(2023, 6, 16),
                date(2023, 6, 16),
                date(2023, 6, 16),
                date(2023, 6, 16),
            ],
            "ts_recv": [
                _ts(2023, 6, 14, 13, 30),
                _ts(2023, 6, 14, 13, 31),
                _ts(2023, 6, 14, 13, 32),
                _ts(2023, 6, 14, 23, 0),
                _ts(2023, 6, 15, 0, 0),
                _ts(2023, 6, 15, 13, 30),
                _ts(2023, 6, 15, 13, 31),
                _ts(2023, 6, 15, 13, 32),
                _ts(2023, 6, 15, 14, 0),
                _ts(2023, 6, 15, 23, 0),
                _ts(2023, 6, 16, 0, 0),
                _ts(2023, 6, 16, 13, 30),
                _ts(2023, 6, 16, 13, 31),
                _ts(2023, 6, 16, 13, 32),
                _ts(2023, 6, 16, 13, 33),
            ],
            "ts_recv_et": [
                _ts(2023, 6, 14, 13, 30),
                _ts(2023, 6, 14, 13, 31),
                _ts(2023, 6, 14, 13, 32),
                _ts(2023, 6, 14, 23, 0),
                _ts(2023, 6, 15, 0, 0),
                _ts(2023, 6, 15, 13, 30),
                _ts(2023, 6, 15, 13, 31),
                _ts(2023, 6, 15, 13, 32),
                _ts(2023, 6, 15, 14, 0),
                _ts(2023, 6, 15, 23, 0),
                _ts(2023, 6, 16, 0, 0),
                _ts(2023, 6, 16, 13, 30),
                _ts(2023, 6, 16, 13, 31),
                _ts(2023, 6, 16, 13, 32),
                _ts(2023, 6, 16, 13, 33),
            ],
            "is_overnight": [
                False,
                False,
                False,
                True,
                True,
                False,
                False,
                False,
                False,
                True,
                True,
                False,
                False,
                False,
                False,
            ],
            "is_rth": [
                True,
                True,
                True,
                False,
                False,
                True,
                True,
                True,
                True,
                False,
                False,
                True,
                True,
                True,
                True,
            ],
            "side": [
                "A",
                "B",
                "A",
                "A",
                "B",
                "A",
                "B",
                "A",
                "N",
                "A",
                "B",
                "A",
                "B",
                "N",
                "N",
            ],
            "price": [
                100.00,
                100.25,
                100.50,
                101.00,
                100.75,
                102.00,
                102.25,
                102.50,
                None,
                101.00,
                101.25,
                103.00,
                103.25,
                None,
                None,
            ],
            "size": [
                10.0,
                30.0,
                20.0,
                15.0,
                5.0,
                10.0,
                15.0,
                20.0,
                0.0,
                12.0,
                18.0,
                30.0,
                10.0,
                0.0,
                0.0,
            ],
            "bid_px_00": [
                99.75,
                100.00,
                100.25,
                100.75,
                100.50,
                101.75,
                102.00,
                102.25,
                102.00,
                100.75,
                101.00,
                102.75,
                103.00,
                103.10,
                None,
            ],
            "ask_px_00": [
                100.25,
                100.50,
                100.75,
                101.25,
                101.00,
                102.25,
                102.50,
                102.75,
                102.50,
                101.25,
                101.50,
                103.25,
                103.50,
                None,
                103.30,
            ],
            "front_symbol": ["NQU3"] * 15,
        },
        strict=False,
    )


def test_overnight_profile_uses_completed_globex_rows_only() -> None:
    result = build_overnight_profiles(_session_fixture())

    june_15 = result.filter(pl.col("trading_date") == date(2023, 6, 15)).row(0, named=True)

    assert {
        "overnight_poc",
        "overnight_vah",
        "overnight_val",
        "bucket_size",
        "profile_trade_rows",
        "quality_status",
    }.issubset(result.columns)
    assert june_15["profile_trade_rows"] == 2
    assert june_15["profile_total_volume"] == 20.0
    assert june_15["bucket_prices"] == [100.75, 101.0]
    assert june_15["bucket_volumes"] == [5.0, 15.0]
    assert june_15["overnight_poc"] == 101.0
    assert june_15["overnight_val"] == 101.0
    assert june_15["overnight_vah"] == 101.0


def test_daily_profiles_build_tick_aligned_histograms_and_prior_day_levels() -> None:
    result = build_daily_rth_profiles(_session_fixture())

    june_15 = result.filter(pl.col("trading_date") == date(2023, 6, 15)).row(0, named=True)

    assert {
        "prior_rth_poc",
        "prior_rth_vah",
        "prior_rth_val",
        "bucket_prices",
        "bucket_volumes",
    }.issubset(result.columns)
    assert june_15["bucket_size"] == 0.25
    assert june_15["bucket_prices"] == [102.0, 102.25, 102.5]
    assert june_15["bucket_volumes"] == [10.0, 15.0, 20.0]
    assert june_15["daily_rth_poc"] == 102.5
    assert june_15["prior_rth_poc"] == 100.25
    assert june_15["prior_rth_val"] == 100.25
    assert june_15["prior_rth_vah"] == 100.5


def test_htf_composite_excludes_current_session_and_tracks_window_coverage() -> None:
    daily_profiles = build_daily_rth_profiles(_htf_fixture())

    result = build_htf_profiles(daily_profiles)
    june_16 = result.filter(pl.col("trading_date") == date(2023, 6, 16)).row(0, named=True)

    assert {
        "htf_poc",
        "htf_vah",
        "htf_val",
        "source_session_count",
        "window_target_sessions",
        "window_complete",
        "roll_mixed_window",
        "source_front_symbols",
    }.issubset(result.columns)
    assert june_16["source_session_count"] == 2
    assert june_16["window_target_sessions"] == 180
    assert june_16["window_complete"] is False
    assert june_16["roll_mixed_window"] is False
    assert june_16["source_front_symbols"] == ["NQU3"]
    assert june_16["bucket_prices"] == [100.0, 100.25, 100.5, 101.0, 101.25, 101.5]
    assert june_16["htf_poc"] == 101.25
    assert june_16["quality_status"] == "insufficient_history"


def test_htf_composite_nulls_levels_when_roll_window_contains_multiple_front_symbols() -> None:
    result = build_htf_profiles(_mixed_roll_daily_profiles(), lookback_sessions=2, min_full_window_sessions=2)

    september_20 = result.filter(pl.col("trading_date") == date(2023, 9, 20)).row(0, named=True)

    assert september_20["roll_mixed_window"] is True
    assert september_20["quality_status"] == "mixed_roll_window"
    assert september_20["htf_poc"] is None
    assert september_20["htf_vah"] is None
    assert september_20["htf_val"] is None
    assert september_20["lvn_prices"] == []
    assert september_20["bucket_prices"] == []
    assert september_20["bucket_volumes"] == []


def test_lvn_detection_prefers_stable_local_minima() -> None:
    result = detect_lvn_prices(
        bucket_prices=[100.0, 100.25, 100.5, 100.75, 101.0],
        bucket_volumes=[120.0, 40.0, 130.0, 42.0, 125.0],
        min_prominence_ratio=0.20,
    )

    assert result == [100.25, 100.75]


def test_enriched_output_carries_htf_balance_edges_and_quality_status() -> None:
    enriched = attach_volume_profile_levels(_phase7_fixture())

    june_16_trade = enriched.filter(
        (pl.col("trading_date") == date(2023, 6, 16)) & (pl.col("side") == "A")
    ).row(0, named=True)
    june_16_bid_only = enriched.filter(
        (pl.col("trading_date") == date(2023, 6, 16))
        & (pl.col("bid_px_00") == 103.10)
        & pl.col("ask_px_00").is_null()
    ).row(0, named=True)
    june_14 = enriched.filter(pl.col("trading_date") == date(2023, 6, 14)).row(0, named=True)

    assert {
        "overnight_poc",
        "overnight_vah",
        "overnight_val",
        "htf_poc",
        "htf_vah",
        "htf_val",
        "htf_source_session_count",
        "htf_window_complete",
        "htf_roll_mixed_window",
        "htf_nearest_lvn_above",
        "htf_nearest_lvn_below",
        "phase7_nearest_structural_level",
        "phase7_nearest_structural_distance",
        "phase7_levels_within_threshold",
        "phase7_quality_status",
    }.issubset(enriched.columns)
    assert june_16_trade["overnight_poc"] == 101.25
    assert june_16_trade["overnight_vah"] == 101.25
    assert june_16_trade["overnight_val"] == 101.0
    assert june_16_trade["htf_poc"] == 100.25
    assert june_16_trade["htf_vah"] == 102.25
    assert june_16_trade["htf_val"] == 100.0
    assert june_16_trade["htf_source_session_count"] == 2
    assert june_16_trade["htf_window_complete"] is False
    assert june_16_trade["htf_roll_mixed_window"] is False
    assert june_16_trade["htf_nearest_lvn_above"] is None
    assert june_16_trade["htf_nearest_lvn_below"] is None
    assert june_16_trade["phase7_quality_status"] == "ok"
    assert june_16_bid_only["phase7_reference_price"] == 103.10
    assert june_16_bid_only["phase7_quality_status"] == "ok"
    assert june_14["phase7_quality_status"] == "missing_both"


def test_attach_volume_profile_levels_preserves_phase3_columns_and_assigns_nearest_labels() -> None:
    enriched = attach_volume_profile_levels(_phase7_fixture(), proximity_threshold_points=2.0)

    june_16_trade = enriched.filter(
        (pl.col("trading_date") == date(2023, 6, 16)) & (pl.col("price") == 103.0)
    ).row(0, named=True)

    assert {
        "prior_rth_vah",
        "prior_rth_val",
        "prior_rth_poc",
        "nearest_structural_level",
        "nearest_structural_distance",
        "distance_to_prior_rth_poc",
        "distance_to_prior_rth_vah",
        "distance_to_prior_rth_val",
        "distance_to_overnight_poc",
        "distance_to_overnight_vah",
        "distance_to_overnight_val",
        "distance_to_htf_poc",
        "distance_to_htf_vah",
        "distance_to_htf_val",
        "htf_nearest_lvn_above",
        "htf_nearest_lvn_below",
    }.issubset(enriched.columns)
    assert june_16_trade["prior_rth_poc"] == 102.5
    assert june_16_trade["prior_rth_vah"] == 102.5
    assert june_16_trade["prior_rth_val"] == 102.25
    assert june_16_trade["nearest_structural_level"] == "prior_rth_vah"
    assert june_16_trade["nearest_structural_distance"] == 0.5
    assert june_16_trade["distance_to_prior_rth_poc"] == 0.5
    assert june_16_trade["distance_to_prior_rth_vah"] == 0.5
    assert june_16_trade["distance_to_prior_rth_val"] == 0.75
    assert june_16_trade["distance_to_overnight_poc"] == 1.75
    assert june_16_trade["distance_to_overnight_vah"] == 1.75
    assert june_16_trade["distance_to_overnight_val"] == 2.0
    assert june_16_trade["distance_to_htf_poc"] == 2.75
    assert june_16_trade["distance_to_htf_vah"] == 0.75
    assert june_16_trade["distance_to_htf_val"] == 3.0
    assert june_16_trade["phase7_nearest_structural_level"] in {
        "prior_rth_poc",
        "prior_rth_vah",
        "prior_rth_val",
        "overnight_poc",
        "overnight_vah",
        "overnight_val",
        "htf_poc",
        "htf_vah",
        "htf_val",
        "htf_lvn_above",
        "htf_lvn_below",
    }
    assert june_16_trade["phase7_nearest_structural_level"] == "prior_rth_poc"
    assert june_16_trade["phase7_nearest_structural_distance"] == 0.5
    assert june_16_trade["phase7_levels_within_threshold"] == 7
