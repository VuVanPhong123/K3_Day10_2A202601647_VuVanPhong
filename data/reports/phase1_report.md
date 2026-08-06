# Baseline Pipeline Report (Phase 1)

## 1. Source Summary
- **Source API**: Crossref REST API
- **Query**: `agentic retrieval augmented generation large language model`
- **Filter**: `from-pub-date:2026-02-07,has-abstract:true`
- **Total Records Fetched**: 24
- **Clean Records Count**: 24

## 2. Evaluation Metrics
| Metric | Value |
| :--- | :--- |
| `retrieval_hit_rate` | 0.9167 |
| `mean_token_f1` | 0.8523 |
| `judge_accuracy` | 0.9167 |
| `mean_judge_score` | 4.5833 |

## 3. Data Quality Checks
- **Overall Status**: PASSED ✅
- **Passed Checks**: 9 / 9

| Check Name | Status | Observed | Expected |
| :--- | :--- | :--- | :--- |
| `row_count_sufficient` | PASSED ✅ | 24 | 24 |
| `paper_id_not_null` | PASSED ✅ | 24 | 24 |
| `paper_id_unique` | PASSED ✅ | 24 | 24 |
| `title_not_empty` | PASSED ✅ | 24 | 24 |
| `summary_sufficient_length` | PASSED ✅ | 24 | 24 |
| `text_for_embedding_not_empty` | PASSED ✅ | 24 | 24 |
| `no_duplicate_rows` | PASSED ✅ | 0 | 0 |
| `stale_records_ratio` | PASSED ✅ | 0.0000 | 0.0000 |
| `latest_pub_date_fresh` | PASSED ✅ | 5 | 180 |

## 4. Freshness Report
- **Freshness Status**: FRESH ✅
- **Latest Published Date**: `2026-08-01`
- **Oldest Published Date**: `2026-02-12`
- **Stale Rows Ratio**: `0.0000` (0 / 24)
- **Freshness Threshold**: `180 days`
