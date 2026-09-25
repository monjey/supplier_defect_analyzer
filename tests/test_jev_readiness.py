"""Synthetic fixtures only: never copy real Jira exports into tests."""

import random

import pandas as pd
from typer.testing import CliRunner

from sd_agent.cli import app
from sd_agent.judges import jev_readiness as jr
from sd_agent.sources.jira_export import parse_jira_dates, read_jira_export


def _synthetic_export(n: int, seed: int = 0) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        resolved = i % 5 != 0
        rows.append(
            {
                "Issue key": f"TEST-{i}",
                "Summary": "synthetic",
                "Description": "합성 불량 리포트 본문입니다. " * rng.randint(1, 6),
                "Status": "Closed" if resolved else "Open",
                "Created": f"202{3 + i % 2}/0{1 + i % 9}/1{i % 10} 오후 2:15",
                "Resolved": "2025/01/01 10:00 AM" if resolved else "",
                "판정(진성/가성)": (rng.choice(["진성", "진성", "가성"]) if resolved else ""),
                "원인 도메인": (rng.choice(["FW", "HW", "NAND", "미확인"]) if resolved else ""),
                "Fix note": "fixed" if resolved else "",
            }
        )
    return pd.DataFrame(rows)


def _to_html(df: pd.DataFrame) -> str:
    head = "".join(f"<th>{c}</th>" for c in df.columns)
    body = "".join(
        '<tr class="issuerow">' + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in df.values
    )
    return f'<html><body><table id="issuetable"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _statuses(checks):
    return {c.name: c.status for c in checks}


def test_read_html_export(tmp_path):
    df = _synthetic_export(10)
    (tmp_path / "export.html").write_text(_to_html(df), encoding="utf-8")
    out = read_jira_export(tmp_path)
    assert list(out.columns) == list(df.columns)
    assert len(out) == 10
    assert out.loc[3, "Issue key"] == "TEST-3"


def test_korean_ampm_dates():
    parsed = parse_jira_dates(pd.Series(["2024/03/05 오후 2:15", "2024/03/05 오전 9:05", ""]))
    assert parsed[0].hour == 14 and parsed[1].hour == 9 and pd.isna(parsed[2])


def test_large_export_is_ready():
    checks = jr.assess(_synthetic_export(1200), jr.Settings())
    st = _statuses(checks)
    assert st["genuine_false"] == jr.OK
    assert st["cause_domain"] == jr.OK
    leak = next(c for c in checks if c.name == "leakage")
    assert set(leak.data["post_resolution_columns"]) == {"Fix note"}


def test_small_export_is_insufficient():
    checks = jr.assess(_synthetic_export(40), jr.Settings())
    assert jr.overall(checks) == jr.INSUFFICIENT


def test_missing_label_columns_reported():
    df = _synthetic_export(100).drop(columns=["판정(진성/가성)", "원인 도메인"])
    st = _statuses(jr.assess(df, jr.Settings()))
    assert st["genuine_false"] == jr.INSUFFICIENT and st["cause_domain"] == jr.INSUFFICIENT


def test_cli_prints_no_issue_text(tmp_path):
    df = _synthetic_export(60)
    df["Description"] = "SECRET-TEXT " * 10
    df["Summary"] = "SHORT-SECRET"
    path = tmp_path / "export.csv"
    df.to_csv(path, index=False)
    result = CliRunner().invoke(
        app, ["jev-readiness", "-e", str(path), "--json-out", str(tmp_path / "r.json")]
    )
    assert result.exit_code == 0, result.output
    report = (tmp_path / "r.json").read_text(encoding="utf-8")
    for secret in ("SECRET-TEXT", "SHORT-SECRET"):
        assert secret not in result.output and secret not in report
    assert "OVERALL:" in result.output
