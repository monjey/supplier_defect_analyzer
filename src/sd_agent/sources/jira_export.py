"""Read Jira issue-navigator exports (HTML or CSV) into a string-typed DataFrame."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

EXPORT_SUFFIXES = {".html", ".htm", ".csv"}

# Candidate header names per logical field (compared case-insensitively).
FIELD_ALIASES: dict[str, list[str]] = {
    "key": ["issue key", "key", "issuekey", "키", "이슈 키"],
    "summary": ["summary", "요약"],
    "description": ["description", "설명"],
    "status": ["status", "상태"],
    "resolution": ["resolution", "해결", "해결책"],
    "created": ["created", "생성일", "생성됨", "만듦"],
    "resolved": ["resolved", "resolutiondate", "해결일", "해결됨"],
}


def read_jira_export(path: str | Path) -> pd.DataFrame:
    """Read one export file, or every export file directly inside a directory."""
    path = Path(path)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.suffix.lower() in EXPORT_SUFFIXES)
        if not files:
            raise FileNotFoundError(f"no .html/.htm/.csv export in {path}")
        return pd.concat([_read_file(p) for p in files], ignore_index=True)
    return _read_file(path)


def _read_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        # Jira CSV repeats headers for multi-valued fields; pandas suffixes them (.1, .2, ...).
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    return _read_html(path)


def _read_html(path: Path) -> pd.DataFrame:
    soup = BeautifulSoup(path.read_bytes(), "lxml")
    table = soup.find("table", id="issuetable")
    if table is None:
        tables = soup.find_all("table")
        if not tables:
            raise ValueError(f"no <table> in {path}")
        table = max(tables, key=lambda t: len(t.find_all("tr")))

    rows = table.find_all("tr")
    header_row = next((r for r in rows if r.find("th")), None)
    if header_row is None:
        raise ValueError(f"issue table in {path} has no header row")
    headers = _dedupe(
        [th.get_text(" ", strip=True) or th.get("data-id", "") for th in header_row.find_all("th")]
    )

    records = []
    for row in rows:
        if row is header_row:
            continue
        cells = row.find_all("td")
        if not cells:
            continue
        values = [c.get_text(" ", strip=True) for c in cells]
        values = (values + [""] * len(headers))[: len(headers)]
        records.append(values)
    return pd.DataFrame(records, columns=headers, dtype=str)


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for name in names:
        name = name or "column"
        n = seen.get(name, 0)
        out.append(name if n == 0 else f"{name}.{n}")
        seen[name] = n + 1
    return out


def find_column(df: pd.DataFrame, field: str, override: str | None = None) -> str | None:
    """Resolve a logical field to a column name; an explicit override must exist."""
    if override:
        if override not in df.columns:
            raise KeyError(f"column {override!r} not in export (columns: {list(df.columns)})")
        return override
    lowered = {c.casefold(): c for c in df.columns}
    for alias in FIELD_ALIASES.get(field, []):
        if alias in lowered:
            return lowered[alias]
    return None


_KO_AMPM = re.compile(r"(오전|오후)\s*(\d{1,2}:\d{2})")


def parse_jira_dates(values: pd.Series) -> pd.Series:
    """Parse Jira display dates (e.g. '2024/03/05 2:15 PM', '05/Mar/24 2:15 PM', '24/03/05 오후 2:15')."""
    normalized = (
        values.fillna("")
        .astype(str)
        .str.replace(_KO_AMPM, lambda m: f"{m.group(2)} {'AM' if m.group(1) == '오전' else 'PM'}", regex=True)
    )
    return pd.to_datetime(normalized.where(normalized != ""), errors="coerce", format="mixed")
