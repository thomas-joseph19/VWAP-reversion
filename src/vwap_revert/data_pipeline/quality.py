"""Data quality and gap reporting helpers."""

from __future__ import annotations

from datetime import date

import polars as pl


def detect_day_gaps(
    trading_dates: list[date],
    expected_dates: list[date],
    holiday_dates: set[date],
) -> dict:
    """Separate missing trading dates from expected holiday closures."""

    observed = set(trading_dates)
    missing = sorted(day for day in expected_dates if day not in observed)
    holidays = sorted(day for day in missing if day in holiday_dates)
    missing_trading_dates = [day for day in missing if day not in holiday_dates]
    return {
        "missing_trading_dates": missing_trading_dates,
        "holiday_dates": holidays,
    }


def detect_intraday_gaps(df: pl.DataFrame, max_rth_gap_seconds: int = 300) -> pl.DataFrame:
    """Report large intra-session gaps inside RTH."""

    if df.is_empty():
        return pl.DataFrame(
            {
                "trading_date": [],
                "gap_start": [],
                "gap_end": [],
                "gap_seconds": [],
                "is_unusable": [],
            },
            schema={
                "trading_date": pl.Date,
                "gap_start": pl.Datetime("ns", "America/New_York"),
                "gap_end": pl.Datetime("ns", "America/New_York"),
                "gap_seconds": pl.Int64,
                "is_unusable": pl.Boolean,
            },
        )

    rth = df.filter(pl.col("session_name") == "rth").sort(["trading_date", "ts_recv_et"])
    if rth.is_empty():
        return pl.DataFrame(
            {
                "trading_date": [],
                "gap_start": [],
                "gap_end": [],
                "gap_seconds": [],
                "is_unusable": [],
            },
            schema={
                "trading_date": pl.Date,
                "gap_start": pl.Datetime("ns", "America/New_York"),
                "gap_end": pl.Datetime("ns", "America/New_York"),
                "gap_seconds": pl.Int64,
                "is_unusable": pl.Boolean,
            },
        )

    return (
        rth.with_columns(
            pl.col("ts_recv_et").shift(1).over("trading_date").alias("prior_ts_recv_et")
        )
        .with_columns(
            (
                pl.col("ts_recv_et").dt.epoch("s") - pl.col("prior_ts_recv_et").dt.epoch("s")
            ).alias("gap_seconds")
        )
        .filter(pl.col("gap_seconds") > max_rth_gap_seconds)
        .select(
            "trading_date",
            pl.col("prior_ts_recv_et").alias("gap_start"),
            pl.col("ts_recv_et").alias("gap_end"),
            "gap_seconds",
            (pl.col("gap_seconds") > max_rth_gap_seconds).alias("is_unusable"),
        )
    )


def build_quality_report(
    *,
    trading_dates: list[date],
    expected_dates: list[date],
    holiday_dates: set[date],
    intraday_gaps: pl.DataFrame,
    recoverable_row_issues: dict[str, int],
    examples: dict[str, list[str]],
    contract_map: pl.DataFrame | None = None,
    session_df: pl.DataFrame | None = None,
) -> dict:
    """Serialize day-level and row-level quality findings."""

    day_gap_report = detect_day_gaps(trading_dates, expected_dates, holiday_dates)
    unusable_days = sorted(
        {
            *intraday_gaps.filter(pl.col("is_unusable"))["trading_date"].to_list(),
        }
    )

    if contract_map is None:
        unusable_days.append("missing_contract_map")
    if session_df is not None:
        rth_counts = (
            session_df.group_by("trading_date")
            .agg(pl.col("is_rth").sum().alias("rth_rows"))
            .filter(pl.col("rth_rows") == 0)
        )
        unusable_days.extend(day.isoformat() for day in rth_counts["trading_date"].to_list())

    return {
        "missing_trading_dates": [day.isoformat() for day in day_gap_report["missing_trading_dates"]],
        "holiday_dates": [day.isoformat() for day in day_gap_report["holiday_dates"]],
        "unusable_days": [str(day) for day in sorted(set(unusable_days), key=str)],
        "recoverable_row_issues": recoverable_row_issues,
        "examples": examples,
        "intraday_gaps": [
            {
                "trading_date": row["trading_date"].isoformat(),
                "gap_start": row["gap_start"].isoformat(),
                "gap_end": row["gap_end"].isoformat(),
                "gap_seconds": row["gap_seconds"],
                "is_unusable": row["is_unusable"],
            }
            for row in intraday_gaps.to_dicts()
        ],
    }

