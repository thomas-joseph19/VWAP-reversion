"""Partitioned Parquet cache helpers."""

from __future__ import annotations

from pathlib import Path

import polars as pl


def write_canonical_cache(df: pl.DataFrame, output_dir: Path) -> None:
    """Write the canonical phase-1 parquet dataset partitioned by trading_date."""

    output_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(
        output_dir,
        use_pyarrow=True,
        compression="zstd",
        pyarrow_options={"partition_cols": ["trading_date"]},
    )


def scan_canonical_cache(output_dir: Path) -> pl.LazyFrame:
    """Reload the canonical cache lazily."""

    return pl.scan_parquet(output_dir, hive_partitioning=True)
