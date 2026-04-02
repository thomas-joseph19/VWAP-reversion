from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from vwap_revert.data_pipeline.contracts import (
    add_contract_trading_date,
    apply_contract_map,
    build_daily_contract_map,
)


def _sample_contract_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts_recv": [
                "2024-03-08T22:30:00.000000000Z",
                "2024-03-08T23:00:00.000000000Z",
                "2024-03-09T00:00:00.000000000Z",
                "2024-03-10T23:30:00.000000000Z",
                "2024-03-10T23:31:00.000000000Z",
                "2024-03-11T13:31:00.000000000Z",
            ],
            "side": ["A", "A", "B", "A", "B", "A"],
            "size": [10.0, 15.0, 20.0, 5.0, 7.0, 30.0],
            "symbol": ["NQH4", "NQH4", "NQM4", "NQH4", "NQH4", "NQM4"],
        }
    ).with_columns(pl.col("ts_recv").str.strptime(pl.Datetime("ns", "UTC"), strict=True))


def test_contract_trading_date_uses_globex_boundary() -> None:
    frame = pl.DataFrame(
        {
            "ts_recv": [
                "2024-03-08T22:59:59.000000000Z",
                "2024-03-08T23:00:00.000000000Z",
            ],
            "side": ["A", "A"],
            "size": [1.0, 1.0],
            "symbol": ["NQH4", "NQH4"],
        }
    ).with_columns(pl.col("ts_recv").str.strptime(pl.Datetime("ns", "UTC"), strict=True))

    labeled = add_contract_trading_date(frame)

    assert labeled["trading_date"].to_list() == [date(2024, 3, 8), date(2024, 3, 9)]


def test_front_month_selected_by_daily_volume() -> None:
    contract_map = build_daily_contract_map(_sample_contract_frame())

    assert contract_map["front_symbol"].to_list() == ["NQH4", "NQM4", "NQM4"]


def test_roll_map_records_symbol_changes() -> None:
    contract_map = build_daily_contract_map(_sample_contract_frame())

    assert contract_map["is_roll"].to_list() == [False, True, False]
    assert contract_map["prior_symbol"].to_list() == [None, "NQH4", "NQM4"]


def test_front_month_failure_when_no_trade_rows_exist() -> None:
    frame = pl.DataFrame(
        {
            "ts_recv": ["2024-03-08T14:30:00.000000000Z"],
            "side": ["N"],
            "size": [0.0],
            "symbol": ["NQH4"],
        }
    ).with_columns(pl.col("ts_recv").str.strptime(pl.Datetime("ns", "UTC"), strict=True))

    with pytest.raises(ValueError, match="Unable to determine front-month contract"):
        build_daily_contract_map(frame)


def test_apply_contract_map_requires_daily_mapping() -> None:
    frame = add_contract_trading_date(_sample_contract_frame())
    contract_map = pl.DataFrame(
        {
            "trading_date": [date(2024, 3, 9)],
            "front_symbol": ["NQM4"],
            "trade_volume": [20.0],
            "is_roll": [False],
            "prior_symbol": [None],
        }
    )

    with pytest.raises(ValueError, match="Missing contract map"):
        apply_contract_map(frame, contract_map)
