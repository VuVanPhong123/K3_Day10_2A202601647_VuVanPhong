# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
|---|---|
| Khóa/Lớp | K3 |
| Tên nhóm | Nhóm Day 10 – Data Pipeline & Data Observability |
| Repository | `VuVanPhong123/K3_Day10_2A202601647_VuVanPhong` |
| Ngày hoàn thành | 2026-08-06 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
|---:|---|---|---|---|
| 1 | Vũ Văn Phong | 2A202601647 | Pipeline integration & evidence owner | `config.py`, `llm.py`, `phase1.py`, `corruption_flow.py`, integration tests |
| 2 | Hoàng Lê Minh | 2A202601653 | Raw ingestion owner | `crossref.py`, raw response và raw records |
| 3 | Nguyễn Quang Vinh | 2A202601517 | Cleaning & evaluation-set owner | `cleaning.py`, `testset.py`, clean dataset và test set |
| 4 | Phạm Sỹ Đức | 2A202601601 | Data corruption owner | `corruption.py`, corrupted dataset và corruption log |
| 5 | Đoàn Nhật Nam | 2A202601123 | Observability & reporting owner | `quality.py`, `reporting.py`, quality/freshness artifacts |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành pipeline dữ liệu end-to-end cho hệ thống RAG sử dụng dữ liệu bài báo từ Crossref. Pipeline lưu raw response và parsed records, làm sạch thành corpus 24 bản ghi, tạo embedding bằng `sentence-transformers/all-MiniLM-L6-v2`, lập chỉ mục bằng ChromaDB và đánh giá bằng một test set cố định gồm 12 câu hỏi. Baseline đạt retrieval hit rate `1.0`, mean token F1 `0.75`, judge accuracy `0.75` và mean judge score `4`; đồng thời pass 11/11 quality checks và freshness PASS.

Nhóm sau đó tạo các lỗi có kiểm soát như drop document, blank summary, inject noise, truncate title, stale date và duplicate rows. Corrupted dataset làm retrieval hit rate giảm còn `0.25`, token F1 còn khoảng `0.0325`, judge accuracy còn `0.0`, quality chỉ pass 8/11 và stale ratio tăng lên `0.3077`. Repair được thực hiện từ raw snapshot thay vì sao chép baseline clean file. Sau repair, dataset trở về 24 rows, pass 11/11 checks và toàn bộ core metrics trở lại baseline. Hạn chế chính là corpus còn nhỏ, test set được tạo từ chính corpus và Ragas chưa có kết quả đồng nhất cho cả ba trạng thái.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> controlled corruption
    -> re-index và re-evaluate
    -> repair từ raw snapshot
    -> comparison report
```

| Khối | Input | Xử lý chính | Output/artifact | Owner |
|---|---|---|---|---|
| Ingestion | Crossref query/filter | Fetch, retry/backoff, parse | `data/raw/` | Hoàng Lê Minh |
| Cleaning | Raw records | Normalize, validate, deduplicate, derive fields | `data/clean/` | Nguyễn Quang Vinh |
| Embedding/index | `text_for_embedding` | MiniLM embedding, Chroma collection | `data/embeddings/`, local Chroma | Vũ Văn Phong (integration) |
| Evaluation | Clean/index + test set | Retrieval, answer generation, token F1, LLM judge, Ragas | `data/results/` | Vũ Văn Phong |
| Observability | DataFrame và dates | Quality/freshness checks | `data/quality/` | Đoàn Nhật Nam |
| Corruption | Clean dataset + target IDs | Drop/blank/noise/truncate/stale/duplicate | Corrupted data và log | Phạm Sỹ Đức |
| Repair/orchestration | Raw snapshot và test set | Re-clean, rebuild index, re-evaluate | Repaired metrics/report | Vũ Văn Phong |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
|---|---|
| `LLM_PROVIDER` | `gemini` |
| `LLM_MODEL` | `gemini-3.5-flash-lite` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Crossref records | 24 raw / 24 clean |
| Evaluation samples | 12 |
| Freshness threshold | 180 ngày |
| Ragas version | 0.4.3 |

```bash
uv sync --extra dev
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

| Lệnh | Trạng thái | Bằng chứng |
|---|---|---|
| Baseline pipeline | Thành công | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption/repair flow | Thành công | `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

Nguồn dữ liệu là Crossref REST API với query `agentic retrieval augmented generation large language model` và filter yêu cầu publication date gần đây cùng abstract. Module ingestion có timeout, retry cho 429/5xx, exponential backoff và lưu cả response gốc lẫn parsed records.

Clean schema gồm:

`paper_id, title, summary, authors_joined, categories_joined, published, updated, age_days, summary_chars, text_for_embedding, abs_url, pdf_url`.

Cleaning chuẩn hóa whitespace, tác giả và categories; parse ngày; loại record thiếu ID/title/summary; deduplicate theo paper ID và normalized title; tính `age_days`, `summary_chars`; và ghép nội dung thành `text_for_embedding`. Document identity được giữ ổn định qua DOI/paper ID.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
|---|---|
| Số câu hỏi | 12 |
| Question types | Summary, authors, published date, categories |
| Ground-truth IDs | Lấy từ paper ID của clean corpus |
| Embedding model | `all-MiniLM-L6-v2` |
| Vector store | ChromaDB; collection riêng cho baseline/corrupted/repaired |
| LLM provider/model | Gemini / `gemini-3.5-flash-lite` |
| Test set chung | `data/eval/test_set.json` |

Test set được giữ nguyên cho cả ba trạng thái để thay đổi metric chỉ phản ánh thay đổi của corpus, không bị nhiễu bởi thay đổi câu hỏi hoặc ground truth.

## 7. Kết quả baseline

| Artifact | Đường dẫn | Trạng thái |
|---|---|---|
| Raw response/records | `data/raw/` | Có |
| Cleaned dataset | `data/clean/` | Có |
| Embedding manifest/index | `data/embeddings/` | Có |
| Evaluation set | `data/eval/test_set.json` | Có |
| Baseline metrics | `data/results/baseline_metrics.json` | Có |
| Quality/freshness | `data/quality/` | Có |
| Baseline report | `data/reports/phase1_report.md` | Có |

| Metric | Giá trị | Diễn giải |
|---|---:|---|
| `retrieval_hit_rate` | 1.0000 | Tất cả mẫu truy xuất được ground-truth document |
| `mean_token_f1` | 0.7500 | Nội dung câu trả lời khớp tốt với ground truth |
| `judge_accuracy` | 0.7500 | 9/12 mẫu đạt theo LLM judge |
| `mean_judge_score` | 4 | Chất lượng trung bình ở mức tốt |
| LLM judge | 12 success, 0 fallback | Provider thật được dùng cho toàn bộ mẫu |

## 8. Data quality và freshness

Baseline pass 11/11 checks, bao gồm row count, non-null/unique ID, title/summary/embedding text, duplicate content, published date, `age_days`, stale ratio và latest-date freshness. Latest publication date là `2026-08-01`, oldest valid date là `2026-02-12`, stale ratio `0.0000` và freshness PASS.

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Tín hiệu/tác động |
|---|---|---|
| Drop document | Loại document, ưu tiên ground-truth IDs | Retrieval hit giảm |
| Blank summary | Xóa summary | Completeness và answer quality giảm |
| Inject noise | Thêm token nhiễu deterministic | Token F1/LLM score giảm |
| Truncate title | Rút ngắn title | Exact lookup/retrieval suy giảm |
| Stale date | Lùi ngày nhiều năm | Freshness FAIL, stale ratio tăng |
| Duplicate rows | Thêm nội dung trùng với ID khác | Duplicate check FAIL, row count tăng |

Corruption log tại `data/results/corruption_log.json` ghi 7 scenario và 13 affected document IDs. Repair đọc `data/raw/crossref_records.json`, chạy lại cleaning, build lại index và đánh giá trên test set cũ; không sao chép baseline clean CSV.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi |
|---|---:|---:|---:|---:|---:|
| `retrieval_hit_rate` | 1.0000 | 0.2500 | 1.0000 | -0.7500 | 100% về baseline |
| `mean_token_f1` | 0.7500 | 0.0325 | 0.7500 | -0.7175 | 100% về baseline |
| `judge_accuracy` | 0.7500 | 0.0000 | 0.7500 | -0.7500 | 100% về baseline |
| `mean_judge_score` | 4 | 1 | 4 | -3 | 100% về baseline |
| Quality checks | PASS 11/11 | FAIL 8/11 | PASS 11/11 | Mất 3 checks | Phục hồi toàn bộ |
| Freshness | PASS, 0.0000 | FAIL, 0.3077 | PASS, 0.0000 | Stale ratio +0.3077 | Phục hồi toàn bộ |

Hai chuỗi nguyên nhân–bằng chứng:

1. Drop/blank/truncate/stale/duplicate nhắm vào evaluation documents → quality/freshness chuyển FAIL → retrieval hit, token F1 và LLM judge giảm mạnh.
2. Repair từ raw snapshot → clean schema, row count và freshness trở lại baseline → toàn bộ core metrics trở lại mức baseline.

## 11. LLM judge và Ragas

LLM judge dùng Gemini `gemini-3.5-flash-lite`. Cả ba trạng thái có 12 lần judge thành công và 0 heuristic fallback.

Baseline Ragas thành công trên 9 mẫu đủ điều kiện: answer relevancy `0.2462`, context precision `0.6667`, context recall `0.6667`, faithfulness `0.6667`; ba category samples bị bỏ qua vì empty answer. Corrupted Ragas có trạng thái `failed` do trả về metric không hợp lệ; đây không phải metric bằng 0. Repaired Ragas được `skipped` vì lần chạy đó không bật `RUN_RAGAS=1`.

## 12. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Các module trên nhiều branch có khác biệt về schema, key báo cáo và cách truyền evaluation document IDs.
- **Nguyên nhân:** Contract chưa được đồng bộ hoàn toàn khi phát triển song song.
- **Cách xử lý:** Chốt clean schema 12 cột, tập trung artifact paths trong `Settings`, dùng một test set chung và truyền `ground_truth_doc_ids` vào corruption.
- **Cách xác minh:** Baseline/corrupted/repaired chạy end-to-end; comparison report khớp với JSON metrics và observability artifacts.

## 13. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Hướng cải thiện |
|---|---|---|
| Corpus chỉ 24 records | Chưa đại diện dữ liệu thực tế | Mở rộng query và số record, theo dõi chi phí/thời gian |
| Test set tạo từ corpus | Có thể thiên lệch | Thêm câu hỏi thủ công/độc lập và nhiều question type |
| Ragas không đồng nhất | Chưa so sánh đủ ba trạng thái | Chạy lại cùng cấu hình và lưu rõ eligible samples |
| ChromaDB local | Chưa phù hợp production | Tách persistent vector service và kiểm thử tải |
| Corruption synthetic | Chưa bao phủ lỗi thực | Thêm schema drift, encoding lỗi, partial update và source outage |

## 14. Phân công và báo cáo cá nhân

- [`2A202601647_VuVanPhong.md`](2A202601647_VuVanPhong.md)
- [`2A202601653_HoangLeMinh.md`](2A202601653_HoangLeMinh.md)
- [`2A202601517_NguyenQuangVinh.md`](2A202601517_NguyenQuangVinh.md)
- [`2A202601601_PhamSyDuc.md`](2A202601601_PhamSyDuc.md)
- [`2A202601123_DoanNhatNam.md`](2A202601123_DoanNhatNam.md)

## 15. Kết luận

Nhóm đã hoàn thành pipeline Crossref RAG có ingestion, cleaning, embedding/index, evaluation, observability, controlled corruption và repair. Kết quả thực tế chứng minh data corruption làm suy giảm đồng thời tín hiệu dữ liệu và chất lượng agent. Khi phục hồi từ raw snapshot, row count, quality, freshness và toàn bộ core metrics quay lại baseline. Điều này cho thấy data lineage, test set cố định và observability là các thành phần quan trọng để vận hành hệ thống AI dựa trên dữ liệu ngoài.
