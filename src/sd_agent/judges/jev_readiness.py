"""Check whether a Jira export has enough labeled evidence to calibrate and validate Jev.

Only aggregates (counts, rates, column names, categorical label values) are reported, so the
output can be shared without exposing issue text. Thresholds follow docs/rlcd_jev_report.md:
isotonic calibration needs "a few hundred" labeled cases and is unstable below ~50, and a
held-out test split must never be used to fit the calibrator or pick thresholds.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import pandas as pd

from sd_agent.sources.jira_export import find_column, parse_jira_dates

OK, MARGINAL, INSUFFICIENT, INFO = "OK", "MARGINAL", "INSUFFICIENT", "INFO"

# Heuristic gates (see module docstring). Per-class minimums apply to each class separately
# because both the calibration fit and the test estimate need both outcomes.
TOTAL_OK, TOTAL_MIN = 300, 50
PER_CLASS_OK, PER_CLASS_MIN = 50, 20
TEST_FRACTION = 0.4  # calibration / test split used for sizing
MIN_TEXT_CHARS = 50
LEAK_FILL_GAP = 0.5  # fill-rate gap (resolved - unresolved) that marks a post-resolution field
MAX_CATEGORICAL = 30
MAX_VALUE_CHARS = 30  # longer values are free text: never print them

DEFAULT_GENUINE = ["진성", "genuine", "true defect", "real defect"]
DEFAULT_FALSE = ["가성", "false", "false defect", "not a defect", "no defect"]
DEFAULT_UNKNOWN = ["unknown", "미확인", "미상", "원인불명", "n/a", "na", "tbd", "판정불가"]


@dataclass
class Check:
    name: str
    status: str
    detail: str
    data: dict = field(default_factory=dict)


@dataclass
class Settings:
    genuine_col: str | None = None
    genuine_values: list[str] = field(default_factory=lambda: list(DEFAULT_GENUINE))
    false_values: list[str] = field(default_factory=lambda: list(DEFAULT_FALSE))
    cause_col: str | None = None
    unknown_values: list[str] = field(default_factory=lambda: list(DEFAULT_UNKNOWN))
    key_col: str | None = None
    created_col: str | None = None
    resolved_col: str | None = None
    description_col: str | None = None


def _norm(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.casefold()


def _filled(s: pd.Series) -> pd.Series:
    return _norm(s) != ""


def _grade(total: int, smallest: int) -> str:
    if total >= TOTAL_OK and smallest >= PER_CLASS_OK:
        return OK
    if total >= TOTAL_MIN and smallest >= PER_CLASS_MIN:
        return MARGINAL
    return INSUFFICIENT


def ece_noise_floor(n: int) -> float:
    """Rough ECE a perfectly calibrated model still shows at test size n (0.045 at n=60, ~1/sqrt(n))."""
    return 0.045 * math.sqrt(60 / n) if n > 0 else float("nan")


def _split_detail(n: int) -> str:
    n_test = int(n * TEST_FRACTION)
    return (
        f"calibration/test split {n - n_test}/{n_test}; test ECE noise floor ~{ece_noise_floor(n_test):.3f}"
    )


def _value_counts(values: pd.Series, limit: int = MAX_CATEGORICAL) -> dict:
    """Counts of short categorical values; free-text values are collapsed so no issue text is shown."""
    values = values.astype(str).str.strip()
    labels = values.where(values.str.len() <= MAX_VALUE_CHARS, f"<free text > {MAX_VALUE_CHARS} chars>")
    return labels.value_counts().head(limit).to_dict()


def column_inventory(df: pd.DataFrame, hide_values: bool = False) -> list[dict]:
    # Summary/description are issue text even when short: never show their values.
    text_cols = {find_column(df, "summary"), find_column(df, "description")}
    rows = []
    for col in df.columns:
        filled = _filled(df[col])
        values = df.loc[filled, col].astype(str).str.strip()
        entry = {"column": col, "fill_rate": round(filled.mean(), 3), "n_unique": int(values.nunique())}
        if not hide_values and col not in text_cols and 0 < entry["n_unique"] <= MAX_CATEGORICAL:
            entry["values"] = _value_counts(values)
        rows.append(entry)
    return rows


def assess(df: pd.DataFrame, settings: Settings) -> list[Check]:
    checks: list[Check] = []
    key = find_column(df, "key", settings.key_col)
    created_col = find_column(df, "created", settings.created_col)
    resolved_col = find_column(df, "resolved", settings.resolved_col)
    desc_col = find_column(df, "description", settings.description_col)

    dup = int(df[key].duplicated().sum()) if key else 0
    checks.append(
        Check(
            "export",
            INFO if key else MARGINAL,
            f"{len(df)} rows, {len(df.columns)} columns; key column: {key or 'NOT FOUND'}; duplicate keys: {dup}",
            {"rows": len(df), "columns": len(df.columns), "duplicate_keys": dup},
        )
    )
    if key and dup:
        df = df.drop_duplicates(subset=key, keep="last")

    created = parse_jira_dates(df[created_col]) if created_col else None
    resolved_mask = _filled(df[resolved_col]) if resolved_col else None

    genuine_col = settings.genuine_col or _guess_column(df, ["진성", "가성", "genuine"])
    if genuine_col:
        checks.append(_check_genuine(df, genuine_col, settings))
    else:
        checks.append(
            Check(
                "genuine_false",
                INSUFFICIENT,
                "no genuine/false column found; pass --genuine-col (see column inventory)",
            )
        )

    cause_col = settings.cause_col or _guess_column(df, ["원인", "root cause", "cause"])
    if cause_col:
        checks.append(_check_cause(df, cause_col, settings, genuine_col))
    else:
        checks.append(
            Check(
                "cause_domain",
                INSUFFICIENT,
                "no cause-domain column found; pass --cause-col (see column inventory)",
            )
        )

    if desc_col:
        checks.append(_check_text(df[desc_col]))
    else:
        checks.append(
            Check(
                "report_text",
                MARGINAL,
                "no description column found; Jev needs the report text (pass --description-col)",
            )
        )

    if resolved_mask is not None:
        checks.append(_check_leakage(df, resolved_mask, exclude={key, resolved_col, genuine_col, cause_col}))

    if created is not None:
        labeled = _labeled_mask(df, genuine_col, cause_col, settings)
        checks.append(_check_time(created, labeled))
    return checks


def _guess_column(df: pd.DataFrame, needles: list[str]) -> str | None:
    for col in df.columns:
        if any(n in col.casefold() for n in needles):
            return col
    return None


def _labeled_mask(df, genuine_col, cause_col, settings) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    if genuine_col:
        v = _norm(df[genuine_col])
        mask |= v.isin(_lower(settings.genuine_values)) | v.isin(_lower(settings.false_values))
    if cause_col:
        v = _norm(df[cause_col])
        mask |= (v != "") & ~v.isin(_lower(settings.unknown_values))
    return mask


def _lower(values: list[str]) -> set[str]:
    return {v.strip().casefold() for v in values}


def _check_genuine(df: pd.DataFrame, col: str, s: Settings) -> Check:
    v = _norm(df[col])
    n_gen = int(v.isin(_lower(s.genuine_values)).sum())
    n_false = int(v.isin(_lower(s.false_values)).sum())
    unmapped = df.loc[(v != "") & ~v.isin(_lower(s.genuine_values) | _lower(s.false_values)), col]
    n = n_gen + n_false
    status = _grade(n, min(n_gen, n_false))
    detail = f"column {col!r}: genuine {n_gen}, false {n_false}, blank {int((v == '').sum())}"
    if len(unmapped):
        detail += f", unmapped {len(unmapped)} (map them with --genuine-values/--false-values)"
    if n:
        detail += f"; {_split_detail(n)}"
    return Check(
        "genuine_false",
        status,
        detail,
        {
            "column": col,
            "genuine": n_gen,
            "false": n_false,
            "unmapped_values": _value_counts(unmapped),
        },
    )


def _check_cause(df: pd.DataFrame, col: str, s: Settings, genuine_col: str | None) -> Check:
    raw = df[col].fillna("").astype(str).str.strip()
    v = raw.str.casefold()
    unknown = v.isin(_lower(s.unknown_values))
    labeled = (v != "") & ~unknown
    multi = int(raw[labeled].str.contains(r"[,;/]").sum())
    counts = raw[labeled].value_counts()
    usable = counts[counts >= PER_CLASS_OK]
    marginal = counts[(counts >= PER_CLASS_MIN) & (counts < PER_CLASS_OK)]
    too_small = counts[counts < PER_CLASS_MIN]
    n = int(labeled.sum())

    kept = counts[counts >= PER_CLASS_MIN]
    if n >= TOTAL_OK and len(usable) >= 2 and usable.sum() >= 0.8 * n:
        status = OK
    elif n >= TOTAL_MIN and len(kept) >= 2:
        status = MARGINAL
    else:
        status = INSUFFICIENT

    detail = (
        f"column {col!r}: {n} labeled across {len(counts)} domains "
        f"({len(usable)} with >= {PER_CLASS_OK}, {len(marginal)} with {PER_CLASS_MIN}-{PER_CLASS_OK - 1}, "
        f"{len(too_small)} with < {PER_CLASS_MIN} -> merge into an 'other' option); "
        f"unknown/undetermined {int(unknown.sum())} (examples for the 'insufficient evidence' option)"
    )
    if multi:
        detail += f"; {multi} cells look multi-valued (Choice needs one domain per case)"
    if n:
        detail += f"; {_split_detail(n)}"

    data = {
        "column": col,
        "domain_counts": _value_counts(raw[labeled], limit=len(counts)),
        "unknown": int(unknown.sum()),
        "multi_valued": multi,
    }
    if genuine_col:
        gv = _norm(df[genuine_col])
        on_false = int((labeled & gv.isin(_lower(s.false_values))).sum())
        data["cause_on_false_defects"] = on_false
        if on_false:
            detail += f"; {on_false} false (가성) defects also carry a cause domain (check label semantics)"
    return Check("cause_domain", status, detail, data)


def _check_text(text: pd.Series) -> Check:
    t = text.fillna("").astype(str).str.strip()
    lengths = t.str.len()
    enough = lengths >= MIN_TEXT_CHARS
    hangul = t.str.count(r"[가-힣]")
    letters = t.str.count(r"[A-Za-z가-힣]").replace(0, 1)
    ko_share = hangul / letters
    lang = pd.cut(ko_share[t != ""], [-0.01, 0.2, 0.8, 1.0], labels=["en", "mixed", "ko"]).value_counts()
    rate = enough.mean() if len(t) else 0.0
    status = OK if rate >= 0.9 else MARGINAL if rate >= 0.6 else INSUFFICIENT
    detail = (
        f"{rate:.0%} of issues have >= {MIN_TEXT_CHARS} chars of description "
        f"(median {int(lengths.median()) if len(t) else 0}); language mix {lang.to_dict()} "
        "(calibrate per input language). Exports show the CURRENT description, which may have been "
        "edited after the report: confirm it reflects report-time information."
    )
    return Check(
        "report_text",
        status,
        detail,
        {"rate_min_chars": round(float(rate), 3), "language_mix": {k: int(c) for k, c in lang.items()}},
    )


def _check_leakage(df: pd.DataFrame, resolved: pd.Series, exclude: set) -> Check:
    if resolved.all() or not resolved.any():
        return Check(
            "leakage",
            INFO,
            "cannot compare resolved vs unresolved fill rates "
            "(export is all one or the other); review fields manually for report_time view",
        )
    suspects = {}
    for col in df.columns:
        if col in exclude:
            continue
        f = _filled(df[col])
        gap = f[resolved].mean() - f[~resolved].mean()
        if gap >= LEAK_FILL_GAP:
            suspects[col] = round(float(gap), 2)
    detail = (
        f"{len(suspects)} columns are mostly filled only after resolution; exclude them from "
        f"Jev inputs and report_time features: {sorted(suspects)}"
        if suspects
        else "no column is filled predominantly after resolution"
    )
    return Check("leakage", INFO, detail, {"post_resolution_columns": suspects})


def _check_time(created: pd.Series, labeled: pd.Series) -> Check:
    parsed = created.notna()
    years = created[parsed & labeled].dt.year.value_counts().sort_index()
    detail = (
        f"created date parsed for {parsed.mean():.0%} of rows; labeled cases per year "
        f"{ {int(y): int(c) for y, c in years.items()} }. Use a time-ordered test split "
        "(newest cases as test) to measure drift."
    )
    status = INFO if parsed.mean() >= 0.9 else MARGINAL
    return Check(
        "time_coverage", status, detail, {"labeled_per_year": {int(y): int(c) for y, c in years.items()}}
    )


def overall(checks: list[Check]) -> str:
    graded = {c.name: c.status for c in checks if c.name in ("genuine_false", "cause_domain")}
    if any(s == INSUFFICIENT for s in graded.values()):
        return INSUFFICIENT
    if any(s == MARGINAL for s in graded.values()):
        return MARGINAL
    return OK


def to_dict(checks: list[Check]) -> dict:
    return {"overall": overall(checks), "checks": [asdict(c) for c in checks]}
