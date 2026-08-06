# Data Corruption & Pipeline Repair Comparison Report

## 1. Metrics Comparison (Absolute & Delta)

| Metric | Baseline | Corrupted | Repaired | Corrupted Delta | Repaired Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `retrieval_hit_rate` | 0.9167 | 0.4167 | 0.9167 | `-0.5000` | `+0.0000` |
| `mean_token_f1` | 0.8523 | 0.3850 | 0.8523 | `-0.4673` | `+0.0000` |
| `judge_accuracy` | 0.9167 | 0.4167 | 0.9167 | `-0.5000` | `+0.0000` |
| `mean_judge_score` | 4.5833 | 2.1500 | 4.5833 | `-2.4333` | `+0.0000` |

## 2. Data Quality Checks Comparison

| State | Overall Status | Passed Checks | Failed Checks |
| :--- | :--- | :--- | :--- |
| **Corrupted** | FAILED ❌ | 5 | 4 |
| **Repaired** | PASSED ✅ | 9 | 0 |

## 3. Freshness Comparison

| State | Freshness Status | Latest Published | Stale Ratio |
| :--- | :--- | :--- | :--- |
| **Corrupted** | STALE ⚠️ | `2024-01-01` | `0.5000` |
| **Repaired** | FRESH ✅ | `2026-08-01` | `0.0000` |

## 4. Analysis & Executive Summary
- **Impact of Corruption**: Injecting noise, truncation, blank abstracts, and stale dates severely degrades retrieval accuracy and LLM answer quality.
- **Recovery via Repair**: Re-ingesting and cleaning raw data from the authoritative source restores data quality checks to 100% success and recovers RAG agent accuracy back to baseline levels.