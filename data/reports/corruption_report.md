# Data Corruption & Pipeline Repair Comparison Report

## Corruption Scenarios
- Scenarios recorded: `7`
- Affected document IDs: `13`

## Metrics Comparison (Corrupted Delta and Repaired Delta)
| Metric | Baseline | Corrupted | Repaired | Corrupted Δ | Repaired Δ |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `samples` | `12` | `12` | `12` | `+0.0000` | `+0.0000` |
| `retrieval_hit_rate` | `1.0000` | `0.2500` | `1.0000` | `-0.7500` | `+0.0000` |
| `mean_token_f1` | `0.7500` | `0.0325` | `0.7500` | `-0.7175` | `+0.0000` |
| `judge_accuracy` | `0.7500` | `0.0000` | `0.7500` | `-0.7500` | `+0.0000` |
| `mean_judge_score` | `4` | `1` | `4` | `-3.0000` | `+0.0000` |
| `judge_provider` | `gemini` | `gemini` | `gemini` | `` | `` |
| `judge_model` | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` | `` | `` |
| `llm_judge_success_count` | `12` | `12` | `12` | `+0.0000` | `+0.0000` |
| `llm_judge_fallback_count` | `0` | `0` | `0` | `+0.0000` | `+0.0000` |
| `ragas` | `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}` | `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}` | `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}` | `` | `` |

## Data Quality Comparison
| State | Status | Passed | Failed | Rows |
| :--- | :--- | ---: | ---: | ---: |
| **Baseline** | `PASS` | `11` | `0` | `24` |
| **Corrupted** | `FAIL` | `8` | `3` | `26` |
| **Repaired** | `PASS` | `11` | `0` | `24` |

## Freshness Comparison
| State | Status | Latest | Stale ratio | Invalid dates |
| :--- | :--- | :--- | ---: | ---: |
| **Baseline** | `PASS` | `2026-08-01` | `0.0000` | `0` |
| **Corrupted** | `FAIL` | `2026-07-03` | `0.3077` | `0` |
| **Repaired** | `PASS` | `2026-08-01` | `0.0000` | `0` |

## Evidence-based Conclusion
- Corruption reduced: `retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score`.
- Repair improved over corrupted for: `retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score`.
- Quality status: baseline `PASS`, corrupted `FAIL`, repaired `PASS`.
- Repair input was the raw-record snapshot and the clean transformation was rerun.
