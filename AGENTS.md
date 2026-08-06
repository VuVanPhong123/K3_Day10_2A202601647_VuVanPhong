# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.11-3.13 lab for a Crossref-backed RAG pipeline. Production code is under `src/`:

- `core/` holds settings, paths, and shared utilities.
- `ingestion/` fetches, cleans, and corrupts Crossref records.
- `retrieval/` builds embeddings/Chroma indexes and runs the agent.
- `evaluation/`, `observability/`, and `pipelines/` respectively measure quality, generate reports, and orchestrate flows.

Use `script/run_phase1.py` for the baseline and `script/run_corruption_flow.py` for corruption, repair, and comparison. Generated artifacts belong in `data/` (such as `data/raw/`, `data/results/`, and `data/reports/`), never `src/`. Lab material is in `Guide.md`, `Rubric.md`, and `report/`.

## Build, Test, and Development Commands

From the repository root, prefer the locked `uv` environment:

```bash
uv sync --extra dev                 # install project and pytest
uv run python script/run_phase1.py  # execute baseline pipeline
uv run python script/run_corruption_flow.py  # execute phase 2 after baseline
uv run pytest                       # run automated tests
rg -n "TODO\(student\)|NotImplementedError" src  # find unfinished lab tasks
```

Alternatively, create a virtual environment and run `python -m pip install -e .`; `requirements.txt` alone does not expose the `src/` packages. Pipelines may need internet access, an embedding-model download, and an LLM provider in `.env`.

## Coding Style & Naming Conventions

Use four-space indentation, `from __future__ import annotations`, and type hints for public functions. Use `snake_case` for functions, modules, and variables; use `PascalCase` for dataclasses such as `Settings`. Keep orchestration in `pipelines/`, reusable logic in its domain module, and reuse `settings.paths` rather than hard-code paths. No formatter or linter is configured; keep changes PEP 8-compatible and narrow.

## Testing Guidelines

`pytest` is the declared development framework, but no `tests/` directory is committed yet. Add focused tests under `tests/` for changed behavior, named `test_<unit>_<expected_behavior>.py`; mock API and LLM calls. Run `uv run pytest` before submitting. For pipeline changes, also run the relevant entry point and verify artifacts and metrics in `data/`.

## Commit, Pull Request & Configuration Guidelines

Recent history uses short messages such as `update`; prefer clearer imperative, scoped subjects, for example `Add freshness validation report`. Keep commits focused. Pull requests should summarize the affected pipeline stage, link the task or issue when available, state validation performed, and include report or metric changes when behavior changes.

Copy `.env.example` to `.env` for local credentials. Never commit `.env`, API keys, generated virtual environments, or cache files.
