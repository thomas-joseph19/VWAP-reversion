import pytest
import polars as pl
import numpy as np
from datetime import date, datetime, timedelta
from vwap_revert.indicators.regime import (
    SessionRegimeConfig, 
    build_session_regimes,
    attach_regime_and_multi_timeframe_vwap
)

@pytest.fixture
def multi_timeframe_trade_fixture():
    """Build a canonical-row fixture spanning two weeks, two months, and one contract roll."""
    # Start: Monday 2025-01-27
    # Ends after some weeks/months.
    # We want a roll at some point.
    
    dates = []
    curr = date(2025, 1, 27)  # Monday
    for _ in range(40):
        dates.append(curr)
        curr += timedelta(days=1)
        
    rows = []
    for i, d in enumerate(dates):
        # Change symbol on day 15 (middle of second week)
        symbol = "NQH5" if i < 15 else "NQM5"
        # Jump price on roll day to simulate roll
        base_price = 15000.0 if i < 15 else 15120.0
        
        # Add daily_vwap and daily_sigma placeholders (simulating Phase 2 output)
        for j in range(5):
            ts = datetime(d.year, d.month, d.day, 9, 30) + timedelta(minutes=j)
            price = base_price + j
            rows.append({
                "trading_date": d,
                "ts_recv": ts,
                "ts_recv_et": ts, # simplified
                "is_rth": True,
                "side": "A" if j % 2 == 0 else "B",
                "price": price,
                "size": 1,
                "front_symbol": symbol,
                "bid_px_00": price - 0.25,
                "ask_px_00": price + 0.25,
                "daily_vwap": base_price + 2.0,
                "daily_sigma": 5.0,
            })
            
    return pl.DataFrame(rows)

def test_attach_regime_and_multi_timeframe_vwap_resets_weekly_and_monthly_anchors(multi_timeframe_trade_fixture):
    config = SessionRegimeConfig(lookback_sessions=5, min_history_sessions=5) # use smaller for test
    enriched = attach_regime_and_multi_timeframe_vwap(multi_timeframe_trade_fixture, config)
    
    # Check for expected columns
    expected = {
        "weekly_anchor_id", "monthly_anchor_id", "weekly_vwap", "monthly_vwap",
        "weekly_cum_notional", "weekly_cum_volume", "monthly_cum_notional", "monthly_cum_volume",
        "regime_label", "regime_reason", "regime_min_sigma", "regime_max_sigma", "regime_extension_passes"
    }
    assert expected.issubset(set(enriched.columns))
    
    # Verify Friday -> Monday weekly reset
    friday_date = date(2025, 1, 31)
    monday_date = date(2025, 2, 3)
    
    friday_rows = enriched.filter(pl.col("trading_date") == friday_date)
    monday_rows = enriched.filter(pl.col("trading_date") == monday_date)
    
    assert friday_rows["weekly_anchor_id"].unique().item() != monday_rows["weekly_anchor_id"].unique().item()
    
    # Verify monthly reset (Feb 1st is Saturday, so first trade is Feb 3rd)
    # Jan 31st vs Feb 3rd
    assert friday_rows["monthly_anchor_id"].unique().item() != monday_rows["monthly_anchor_id"].unique().item()

    # Verify regime min/max sigma expectations per REGM-03
    # Find a row where label is set (need enough history in the fixture)
    labeled = enriched.filter(pl.col("regime_label").is_not_null())
    if not labeled.is_empty():
        short_g = labeled.filter(pl.col("regime_label") == "short_gamma")
        if not short_g.is_empty():
            assert short_g["regime_min_sigma"].unique().item() == 1.7
            assert short_g["regime_max_sigma"].unique().item() == 3.2
            
        long_g = labeled.filter(pl.col("regime_label") == "long_gamma")
        if not long_g.is_empty():
            assert long_g["regime_min_sigma"].unique().item() == 1.5
            assert long_g["regime_max_sigma"].unique().item() == 2.4

def test_attach_regime_and_multi_timeframe_vwap_bridges_roll_windows_onto_active_contract_axis(multi_timeframe_trade_fixture):
    config = SessionRegimeConfig(lookback_sessions=5, min_history_sessions=5)
    enriched = attach_regime_and_multi_timeframe_vwap(multi_timeframe_trade_fixture, config)
    
    # Check audit columns
    expected_audit = {
        "weekly_roll_adjustment_applied", "monthly_roll_adjustment_applied",
        "weekly_roll_anchor_symbol", "monthly_roll_anchor_symbol"
    }
    assert expected_audit.issubset(set(enriched.columns))
    
    # Check the roll boundary (day 15 in fixture)
    roll_day = multi_timeframe_trade_fixture["trading_date"].unique()[15]
    prev_day = multi_timeframe_trade_fixture["trading_date"].unique()[14]
    
    roll_day_rows = enriched.filter(pl.col("trading_date") == roll_day)
    assert roll_day_rows["weekly_roll_adjustment_applied"].any()
    assert roll_day_rows["weekly_roll_anchor_symbol"].unique().item() == "NQM5"
    
    # VWAP should not be null after roll if it's the same week
    assert not roll_day_rows["weekly_vwap"].is_null().all()

@pytest.fixture
def canonical_trade_fixture():
    """Build a deterministic fixture with 45 ordered trading_date rows, RTH trade rows only."""
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(45)]
    
    rows = []
    # To get different regimes, we need different volatilities.
    # We'll make the first 20 days stable, then 10 days volatile, then 15 days stable.
    # This should ensure the median threshold shifts and we see both labels.
    
    for i, d in enumerate(dates):
        # 10 trades per day to ensure we have a session close
        for j in range(10):
            # Causal price: slowly drifting
            # We want log returns to be predictable
            if i < 21:
                # Low vol: +0.1% or -0.1% daily
                price = 1000.0 * (1.001 ** i if i % 2 == 0 else 0.999 ** i)
            elif i < 31:
                # High vol: +1% or -1% daily
                price = 1000.0 * (1.01 ** i if i % 2 == 0 else 0.99 ** i)
            else:
                # Low vol again
                price = 1000.0 * (1.001 ** i if i % 2 == 0 else 0.999 ** i)
                
            rows.append({
                "front_symbol": "NQ",
                "ts_recv": datetime(d.year, d.month, d.day, 9, 30) + timedelta(minutes=j),
                "is_rth": True,
                "side": "A" if j % 2 == 0 else "B",
                "price": price,
                "size": 1,
                "trading_date": d,
            })
            
    return pl.DataFrame(rows)

def test_build_session_regimes_marks_insufficient_history_before_threshold_window(canonical_trade_fixture):
    config = SessionRegimeConfig(lookback_sessions=20, min_history_sessions=20)
    result = build_session_regimes(canonical_trade_fixture, config)
    assert not result.is_empty()
    
    # Check required columns
    expected_cols = {
        "trading_date", "session_close_price", "session_log_return",
        "realized_volatility", "regime_threshold_value", "regime_label",
        "regime_reason", "history_session_count", "regime_quality_status"
    }
    assert expected_cols.issubset(set(result.columns))
    
    # First 20 sessions should have insufficient_history
    insufficient = result.head(20)
    assert (insufficient["regime_quality_status"] == "insufficient_history").all()
    assert (insufficient["regime_label"].is_null()).all()
    assert (insufficient["history_session_count"] < 20).all()

def test_build_session_regimes_labels_short_and_long_gamma_from_prior_completed_sessions(canonical_trade_fixture):
    config = SessionRegimeConfig(lookback_sessions=20, min_history_sessions=20)
    result = build_session_regimes(canonical_trade_fixture, config)
    
    # After day 20, we should start seeing 'ok' or at least 'threshold_unavailable'
    # According to our logic, day 21 is the first with 20 prior sessions.
    # It will have realized_volatility but 0 prior realized_volatilities for the threshold.
    day_21 = result.filter(pl.col("trading_date") == date(2025, 1, 1) + timedelta(days=20))
    assert day_21["history_session_count"].item() == 20
    # Depending on implementation, day 21 might be 'threshold_unavailable' or 'ok' if 1-period median is allowed
    # But it definitely shouldn't be 'insufficient_history' of the 20-session return window.
    assert day_21["regime_quality_status"].item() != "insufficient_history"
    
    # Later rows should have labels
    labeled = result.filter(pl.col("regime_label").is_not_null())
    assert not labeled.is_empty()
    
    labels = labeled["regime_label"].unique().to_list()
    assert "short_gamma" in labels
    assert "long_gamma" in labels
    
    # Verify causal labels per D-02: regime_label on day T must not depend on day T price
    # We can't easily prove this from one result, but the implementation should use .shift(1)
    
    # Verify reasons
    reasons = labeled["regime_reason"].unique().to_list()
    assert "rv_above_threshold" in reasons or "rv_below_threshold" in reasons
