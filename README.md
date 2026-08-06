# Day 10 – Data Pipeline and Data Observability Lab

This lab builds a Crossref-backed RAG corpus, evaluates it, injects controlled data corruption, and repairs the corpus from the raw snapshot.

## Thực hiện

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Hà Duy Anh |
| MSSV | 2A202601511 |
| Khóa/Lớp | K3 |
| Hình thức | Làm cá nhân — tự phụ trách toàn bộ pipeline (ingestion, cleaning, RAG/agent, evaluation, corruption, observability, orchestration) |

## Báo cáo công việc

Báo cáo công việc nằm trong thư mục `report/` ở root:

- [Báo cáo cá nhân — Hà Duy Anh](report/2A202601511_HaDuyAnh.md)

Các báo cáo sinh tự động về dữ liệu và kết quả pipeline vẫn nằm trong `data/reports/`:

- [Baseline data report](data/reports/phase1_report.md)
- [Corruption and repair data report](data/reports/corruption_report.md)

## Requirements

- Python 3.11–3.13
- `uv`
- Internet access for Crossref and the first MiniLM model download
- A Gemini or OpenAI API key for real LLM judging and the optional agent demo

Install the locked environment:

```powershell
uv sync --extra dev
```

Create `.env` from `.env.example`. The default provider is Gemini:

```dotenv
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
GOOGLE_API_KEY=
REQUIRE_LLM_JUDGE=1
```

For OpenAI, set `LLM_PROVIDER=openai`, choose a model available to the account, and provide `OPENAI_API_KEY`. Only the selected provider needs a credential. Never commit `.env` or a key.

## Run the lab

Always run baseline before corruption:

```powershell
$env:REFRESH_SOURCE="1"
$env:REFRESH_TEST_SET="1"
$env:RUN_RAGAS="0"
$env:RUN_AGENT_DEMO="1"
$env:REQUIRE_LLM_JUDGE="1"
uv run python script/run_phase1.py
```

Then run corruption and repair with the same evaluation set:

```powershell
$env:REFRESH_SOURCE="0"
$env:REFRESH_TEST_SET="0"
$env:RUN_RAGAS="0"
$env:RUN_AGENT_DEMO="0"
$env:REQUIRE_LLM_JUDGE="1"
uv run python script/run_corruption_flow.py
```

Enable the real Ragas pass only after the core flows are healthy:

```powershell
$env:RUN_RAGAS="1"
$env:REQUIRE_LLM_JUDGE="1"
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

`REQUIRE_LLM_JUDGE=1` prevents silent heuristic fallback. `RUN_RAGAS=1` reports a failure instead of treating an incompatible dependency or API error as a pass.

## Artifacts

The pipeline writes raw Crossref response/records, clean CSV/JSON, local MiniLM embeddings and Chroma data, the shared evaluation set, baseline/corrupted/repaired answers and metrics, quality/freshness JSON, and generated data reports under `data/`. Repair reads `data/raw/crossref_records.json` and reruns cleaning; it does not copy the baseline clean CSV.

`data/chroma/`, `.env`, `job.txt`, caches and Python bytecode are intentionally ignored.

## Checks

```powershell
uv run pytest -q
python -m compileall src
git diff --check
```
