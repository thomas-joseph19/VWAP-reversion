from __future__ import annotations

from pathlib import Path

import pytest


CSV_HEADER = (
    "ts_recv,ts_event,rtype,publisher_id,instrument_id,side,price,size,flags,sequence,"
    "bid_px_00,ask_px_00,bid_sz_00,ask_sz_00,bid_ct_00,ask_ct_00,symbol\n"
)


@pytest.fixture
def csv_root(tmp_path: Path) -> Path:
    root = tmp_path / "csv"
    root.mkdir()
    return root


@pytest.fixture
def write_csv(csv_root: Path):
    def _write_csv(name: str, rows: list[str]) -> Path:
        path = csv_root / name
        path.write_text(CSV_HEADER + "\n".join(rows) + "\n", encoding="utf-8")
        return path

    return _write_csv

