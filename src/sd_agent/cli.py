from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from sd_agent.judges import jev_readiness as jr
from sd_agent.sources.jira_export import read_jira_export

app = typer.Typer(no_args_is_help=True, help="SD_Agent: outsourced eMMC defect analysis")


@app.callback()
def main() -> None:
    pass


def _split(values: str | None, default: list[str]) -> list[str]:
    return [v for v in (s.strip() for s in values.split(",")) if v] if values else default


@app.command("jev-readiness")
def jev_readiness(
    export: Annotated[
        list[Path], typer.Option("--export", "-e", exists=True, help="Jira HTML/CSV export file or dir")
    ],
    genuine_col: Annotated[
        str | None, typer.Option(help="Column holding the genuine/false (진성/가성) judgement")
    ] = None,
    genuine_values: Annotated[str | None, typer.Option(help="Comma-separated values meaning genuine")] = None,
    false_values: Annotated[str | None, typer.Option(help="Comma-separated values meaning false")] = None,
    cause_col: Annotated[str | None, typer.Option(help="Column holding the root-cause domain")] = None,
    unknown_values: Annotated[
        str | None, typer.Option(help="Comma-separated cause values meaning undetermined")
    ] = None,
    key_col: Annotated[str | None, typer.Option()] = None,
    created_col: Annotated[str | None, typer.Option()] = None,
    resolved_col: Annotated[str | None, typer.Option()] = None,
    description_col: Annotated[str | None, typer.Option()] = None,
    inventory: Annotated[bool, typer.Option(help="Print the column inventory")] = True,
    hide_values: Annotated[bool, typer.Option(help="Hide categorical value counts in the inventory")] = False,
    json_out: Annotated[
        Path | None, typer.Option(help="Also write the result as JSON (keep it under data/)")
    ] = None,
) -> None:
    """Check whether the Jira history has enough labeled cases to calibrate and validate Jev.

    Prints aggregates only (counts, rates, column names, categorical values); no issue text.
    """
    import pandas as pd

    df = pd.concat([read_jira_export(p) for p in export], ignore_index=True)
    settings = jr.Settings(
        genuine_col=genuine_col,
        genuine_values=_split(genuine_values, jr.DEFAULT_GENUINE),
        false_values=_split(false_values, jr.DEFAULT_FALSE),
        cause_col=cause_col,
        unknown_values=_split(unknown_values, jr.DEFAULT_UNKNOWN),
        key_col=key_col,
        created_col=created_col,
        resolved_col=resolved_col,
        description_col=description_col,
    )
    checks = jr.assess(df, settings)
    inv = jr.column_inventory(df, hide_values=hide_values)

    if inventory:
        typer.echo("== Column inventory (fill rate, unique values)")
        for row in inv:
            line = f"  {row['column']!r}: fill {row['fill_rate']:.0%}, unique {row['n_unique']}"
            if "values" in row:
                line += f"  {row['values']}"
            typer.echo(line)
        typer.echo("")
    typer.echo("== Jev readiness")
    for c in checks:
        typer.echo(f"  [{c.status:<12}] {c.name}: {c.detail}")
    typer.echo(f"\nOVERALL: {jr.overall(checks)}")

    if json_out:
        result = jr.to_dict(checks)
        result["inventory"] = inv
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
