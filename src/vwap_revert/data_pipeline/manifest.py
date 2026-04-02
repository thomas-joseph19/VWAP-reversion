"""Raw CSV discovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re


_DATE_PATTERN = re.compile(r"(?P<year>\d{4})[-_]?(?P<month>\d{2})[-_]?(?P<day>\d{2})")


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """A deterministic reference to one raw CSV input."""

    csv_path: Path
    session_date: date
    stem: str


def _derive_session_date(path: Path) -> date:
    match = _DATE_PATTERN.search(path.stem)
    if match is None:
        raise ValueError(f"Unable to derive session date from filename: {path.name}")

    return date(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
    )


def build_manifest(root: Path) -> list[ManifestEntry]:
    """Discover and sort raw CSV files deterministically."""

    if not root.exists():
        raise FileNotFoundError(f"CSV root does not exist: {root}")

    entries = [
        ManifestEntry(csv_path=csv_path, session_date=_derive_session_date(csv_path), stem=csv_path.stem)
        for csv_path in root.glob("*.csv")
    ]
    if not entries:
        raise ValueError("No CSV files found under the provided root")

    return sorted(entries, key=lambda entry: (entry.session_date, entry.stem))

