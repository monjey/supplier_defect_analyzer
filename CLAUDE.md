# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SD_Agent is a CLI pipeline for analyzing defects on outsourced eMMC projects. It uses past Jira defect history as evidence for two proposals about a new defect:
- **Agent A**: whether the defect is genuine or false (진성/가성), using a Random Forest.
- **Agent B**: the root-cause domain, using rules plus similar past cases.

The README and the user-facing text are in Korean.

**Status:** the repository is still mostly a scaffold. What exists: `sources/jira_export.py` (Jira HTML/CSV export reader), `judges/jev_readiness.py`, and a Typer `cli.py` with only the `jev-readiness` command. The other pipeline commands and the `configs/` directory the README mentions do not exist yet. The architecture below is the planned design. Check what actually exists before assuming a module is there.

## Commands

The README targets Windows (`.venv\Scripts\...`). On Linux/macOS, use `.venv/bin/...`.

```
python -m venv .venv && .venv/bin/pip install -e .[dev]     # extras: embed, rest, llm, jev
.venv/bin/pytest                                           # testpaths=tests, pythonpath=src
.venv/bin/pytest tests/test_x.py::test_name                # single test
.venv/bin/ruff check . && .venv/bin/ruff format .          # line-length 110, py311
```

Check whether the Jira history has enough labeled cases to calibrate Jev. It prints aggregates only, no issue text, so the output is safe to share:
```
sd-agent jev-readiness -e <export.html|dir> [--genuine-col ... --cause-col ... --genuine-values 진성 --false-values 가성]
```

Planned pipeline commands, in this order:
```
sd-agent ingest --source configs/sources/osemmc_html.yaml   # Jira export (HTML) -> data/
sd-agent labels derive                                      # derive genuine/false + cause labels
sd-agent index build                                        # similar-case index
sd-agent train --view report_time                           # train Agent A
sd-agent predict --key OSEMMC-1170                          # run both agents on one issue
```

## Planned architecture (`src/sd_agent/`)

- `sources/`: ingest adapters driven by YAML under `configs/sources/`. The first one parses a Jira HTML export with BeautifulSoup/lxml. The optional `rest` extra adds a Jira REST source.
- `labeling/`: derives training labels from resolved Jira history.
- `index/`: similar-case retrieval for Agent B. The optional `embed` extra adds sentence-transformers.
- `agents/`: Agent A (scikit-learn RandomForest, persisted with joblib) and Agent B (rules + retrieved cases).
- `judges/`: LLM-based judgement/verification, via the optional extras `llm` (anthropic) or `jev` (typesafe-sdk).
- `llm/`: LLM client wrappers.
- `train --view report_time`: features should use only the information that was available when the defect was reported. Do not leak fields that were filled in after resolution.

## Data confidentiality

`data/`, `*.html`, and `eMMC_SM2734_Jira_files/` are gitignored because they are confidential supplier and Jira data. Never commit them or copy them into tests. Build test fixtures from synthetic data. Get approval before sending FA or Jira content to an external API.

## Jev (TypeSafe) integration rules

Background and evidence are in `docs/rlcd_jev_report.md`. Jev's RLCD training method is unpublished, and independent audits show its raw probabilities rank answers well but are not reliably calibrated. Follow these rules when using Jev:

- Calibrate `probabilities` with isotonic regression on labeled local data (a few hundred cases, plus a held-out test split). Never threshold the `confidence` field, which is a shape statistic of the distribution and not P(correct). Noul answers have no `confidence` field.
- Report a reliability diagram, ECE (with its noise floor), Brier score, and accuracy-vs-coverage at the candidate thresholds.
- Always include an explicit "insufficient evidence" option. Without one, Jev answers anyway, often at high confidence.
- Do arithmetic, counting, and date math in code (erase-count trends, EXT_CSD pre-EOL/life-time fields, time deltas), and pass Jev the derived facts. Prefer several narrow yes/no questions combined in code over one broad "what is the failure mode?" question.
- Pin the model version (e.g. `jev-1.13.0`). Re-calibrate and re-validate thresholds whenever the version, question wording, option set, input language, or data source changes.
- For ISO 26262 contexts, Jev is advisory/triage only: human review stays in the loop and Jev scores are used to prioritize it. Treat document text as untrusted, because injected text can steer answers.
