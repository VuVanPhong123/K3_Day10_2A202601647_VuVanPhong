# Baseline Pipeline Report (Phase 1)

## Run Metadata
- Timestamp (UTC): ``
- LLM provider/model: `gemini` / `gemini-3.5-flash-lite`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Chroma collection: `papers-baseline`

## Source Summary
- Source API: `Crossref REST API`
- Query: `agentic retrieval augmented generation large language model`
- Filter: `from-pub-date:2026-02-07,has-abstract:true`
- Raw row count: `24`
- Clean row count: `24`

## Clean Schema
`paper_id, title, summary, authors_joined, categories_joined, published, updated, age_days, summary_chars, text_for_embedding, abs_url, pdf_url`

## Evaluation Metrics
| Metric | Value |
| :--- | ---: |
| `samples` | `12` |
| `retrieval_hit_rate` | `1.0000` |
| `mean_token_f1` | `0.7500` |
| `judge_accuracy` | `0.7500` |
| `mean_judge_score` | `4` |
| `judge_provider` | `gemini` |
| `judge_model` | `gemini-3.5-flash-lite` |
| `llm_judge_success_count` | `12` |
| `llm_judge_fallback_count` | `0` |

## LLM Judge
- Provider/model: `gemini` / `gemini-3.5-flash-lite`
- Successful LLM judgments: `12`
- Heuristic fallbacks: `0`

## Ragas
`{'answer_relevancy': 0.18087860467972816, 'status': 'failed', 'error': 'Ragas returned invalid metrics: context_precision, context_recall, faithfulness', 'dependency_version': '0.4.3'}`

## Data Quality
- Status: `PASS`
- Passed/total: `11/11`

| Check | Status | Observed | Expected |
| :--- | :--- | ---: | ---: |
| `row_count_sufficient` | `PASS` | `24` | `3` |
| `paper_id_not_null` | `PASS` | `24` | `24` |
| `paper_id_unique` | `PASS` | `24` | `24` |
| `title_not_empty` | `PASS` | `24` | `24` |
| `summary_sufficient_length` | `PASS` | `24` | `24` |
| `text_for_embedding_not_empty` | `PASS` | `24` | `24` |
| `no_duplicate_rows` | `PASS` | `0` | `0` |
| `published_date_valid` | `PASS` | `24` | `24` |
| `age_days_valid` | `PASS` | `24` | `24` |
| `stale_records_ratio` | `PASS` | `0.0000` | `0.0000` |
| `latest_pub_date_fresh` | `PASS` | `5` | `180` |

## Freshness
- Status: `PASS`
- Latest/oldest valid publication: `2026-08-01` / `2026-02-12`
- Invalid/future dates: `0/0`
- Stale ratio: `0.0000`

## Agent Demo
- Status: `PASS (3 answers)`

## Artifact Paths
- `C:\Users\ADMIN\Personal_proj\AIcodelab\day10\K3_Day10_Data-Pipeline-Data-Observability\data\results\baseline_metrics.json`
- `C:\Users\ADMIN\Personal_proj\AIcodelab\day10\K3_Day10_Data-Pipeline-Data-Observability\data\results\baseline_answers.json`
- `C:\Users\ADMIN\Personal_proj\AIcodelab\day10\K3_Day10_Data-Pipeline-Data-Observability\data\results\agent_demo_answers.json`

## Limitations
- LLM judge and agent demo require the selected provider credentials when enabled.
- Ragas is optional and is reported separately from the core retrieval metrics.
