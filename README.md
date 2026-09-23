# SD_Agent — 외주 과제 불량 분석 에이전트

Jira 불량 이력을 근거로 신규 불량의 **진성/가성**(Agent A, Random Forest)과 **원인 도메인**(Agent B, 룰 + 유사 사례)을 제안하는 CLI 파이프라인입니다.

```
python -m venv .venv && .venv\Scripts\pip install -e .[dev]
.venv\Scripts\sd-agent ingest --source configs/sources/osemmc_html.yaml
.venv\Scripts\sd-agent labels derive
.venv\Scripts\sd-agent index build
.venv\Scripts\sd-agent train --view report_time
.venv\Scripts\sd-agent predict --key OSEMMC-1170
```

설계 문서: `docs/` (플랜 사본) / 설정: `configs/` / 데이터·모델·리포트: `data/` (VCS 제외)
