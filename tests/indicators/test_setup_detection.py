from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
import pytest

from vwap_revert.indicators.setup_detection import (
    attach_setup_detection_features,
    extract_setup_events,
)


def _ts(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _setup_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trading_date": [
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 3),
            ],
            "ts_recv": [
                _ts(2024, 1, 2, 14, 29, 59),
                _ts(2024, 1, 2, 14, 30, 0),
                _ts(2024, 1, 2, 14, 45, 0),
                _ts(2024, 1, 2, 15, 0, 0),
                _ts(2024, 1, 2, 15, 15, 0),
                _ts(2024, 1, 2, 15, 20, 0),
                _ts(2024, 1, 2, 15, 25, 0),
                _ts(2024, 1, 2, 15, 30, 0),
                _ts(2024, 1, 2, 16, 30, 1),
                _ts(2024, 1, 3, 14, 30, 0),
                _ts(2024, 1, 3, 14, 30, 1),
            ],
            "ts_recv_et": [
                _ts(2024, 1, 2, 9, 29, 59),
                _ts(2024, 1, 2, 9, 30, 0),
                _ts(2024, 1, 2, 9, 45, 0),
                _ts(2024, 1, 2, 10, 0, 0),
                _ts(2024, 1, 2, 10, 15, 0),
                _ts(2024, 1, 2, 10, 20, 0),
                _ts(2024, 1, 2, 10, 25, 0),
                _ts(2024, 1, 2, 10, 30, 0),
                _ts(2024, 1, 2, 11, 30, 1),
                _ts(2024, 1, 3, 9, 30, 0),
                _ts(2024, 1, 3, 11, 30, 0),
            ],
            "daily_vwap": [
                100.0,
                100.0,
                100.0,
                100.0,
                100.0,
                100.0,
                None,
                100.0,
                100.0,
                100.0,
                100.0,
            ],
            "daily_sigma": [
                10.0,
                10.0,
                10.0,
                10.0,
                10.0,
                10.0,
                10.0,
                0.0,
                10.0,
                10.0,
                10.0,
            ],
            "structural_reference_price": [
                117.0,
                117.0,
                117.0,
                116.9,
                130.0,
                82.0,
                117.0,
                117.0,
                117.0,
                83.0,
                130.0,
            ],
            "structural_levels_within_threshold": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
            "nearest_structural_level": [
                "prior_rth_vah",
                "prior_rth_vah",
                "prior_rth_vah",
                "prior_rth_vah",
                "prior_rth_poc",
                "prior_rth_val",
                "prior_rth_vah",
                "prior_rth_vah",
                "prior_rth_vah",
                "prior_rth_val",
                "prior_rth_poc",
            ],
            "nearest_structural_distance": [1.0, 1.0, 1.0, 1.1, 0.5, 0.25, 1.0, 1.0, 1.0, 0.5, 0.25],
            "bid_px_00": [116.75, 116.75, 116.75, 116.65, 129.75, 81.75, 116.75, 116.75, 116.75, 82.75, 129.75],
            "ask_px_00": [117.25, 117.25, 117.25, 117.15, 130.25, 82.25, 117.25, 117.25, 117.25, 83.25, 130.25],
        },
        strict=False,
    )


def test_time_window_passes_only_inside_inclusive_bounds() -> None:
    enriched = attach_setup_detection_features(_setup_rows())

    assert enriched["time_window_passes"].to_list() == [
        False,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        True,
        True,
    ]


def test_signed_sigma_distance_uses_inclusive_absolute_thresholds() -> None:
    enriched = attach_setup_detection_features(_setup_rows())
    sigma_by_ts = {
        row["ts_recv_et"]: row
        for row in enriched.select(
            [
                "ts_recv_et",
                "setup_sigma_signed",
                "vwap_extension_passes",
            ]
        ).to_dicts()
    }

    assert sigma_by_ts[_ts(2024, 1, 2, 9, 30, 0)]["setup_sigma_signed"] == 1.7
    assert sigma_by_ts[_ts(2024, 1, 2, 9, 30, 0)]["vwap_extension_passes"] is True
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 0, 0)]["setup_sigma_signed"] == pytest.approx(1.69)
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 0, 0)]["vwap_extension_passes"] is False
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 15, 0)]["setup_sigma_signed"] == 3.0
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 15, 0)]["vwap_extension_passes"] is True
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 20, 0)]["setup_sigma_signed"] == -1.8
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 20, 0)]["vwap_extension_passes"] is True
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 25, 0)]["setup_sigma_signed"] is None
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 25, 0)]["vwap_extension_passes"] is False
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 30, 0)]["setup_sigma_signed"] is None
    assert sigma_by_ts[_ts(2024, 1, 2, 10, 30, 0)]["vwap_extension_passes"] is False


def test_combined_predicate_emits_one_event_per_contiguous_episode() -> None:
    enriched = attach_setup_detection_features(_setup_rows())
    events = extract_setup_events(enriched)

    by_ts = {row["ts_recv_et"]: row for row in enriched.select(["ts_recv_et", "setup_event_emitted", "setup_direction"]).to_dicts()}
    assert by_ts[_ts(2024, 1, 2, 9, 30, 0)]["setup_event_emitted"] is True
    assert by_ts[_ts(2024, 1, 2, 9, 45, 0)]["setup_event_emitted"] is False
    assert by_ts[_ts(2024, 1, 2, 10, 15, 0)]["setup_event_emitted"] is True
    assert by_ts[_ts(2024, 1, 2, 10, 20, 0)]["setup_event_emitted"] is False
    assert by_ts[_ts(2024, 1, 3, 9, 30, 0)]["setup_event_emitted"] is True

    assert by_ts[_ts(2024, 1, 2, 9, 30, 0)]["setup_direction"] == "short"
    assert by_ts[_ts(2024, 1, 2, 10, 20, 0)]["setup_direction"] == "long"
    assert by_ts[_ts(2024, 1, 3, 9, 30, 0)]["setup_direction"] == "long"

    assert events.columns == [
        "trading_date",
        "ts_recv",
        "ts_recv_et",
        "structural_reference_price",
        "daily_vwap",
        "daily_sigma",
        "setup_sigma_signed",
        "setup_direction",
        "nearest_structural_level",
        "nearest_structural_distance",
        "structural_levels_within_threshold",
        "bid_px_00",
        "ask_px_00",
    ]
    assert events["ts_recv_et"].to_list() == [
        _ts(2024, 1, 2, 9, 30, 0),
        _ts(2024, 1, 2, 10, 15, 0),
        _ts(2024, 1, 3, 9, 30, 0),
    ]
    assert events.row(0, named=True)["setup_direction"] == "short"
    assert events.row(2, named=True)["setup_direction"] == "long"
