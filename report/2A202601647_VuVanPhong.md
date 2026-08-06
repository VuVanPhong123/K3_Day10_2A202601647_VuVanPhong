# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Vũ Văn Phong |
| MSSV | 2A202601647 |
| Khóa/Lớp | K3 |
| Tên nhóm | Nhóm Day 10 – Data Pipeline & Data Observability |
| Vai trò chính | Pipeline integration & evidence owner |
| Branch phụ trách | `feat/pipeline-integration` |
| Repository | `VuVanPhong123/K3_Day10_2A202601647_VuVanPhong` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Cấu hình pipeline và LLM | `src/core/config.py`, `src/retrieval/llm.py` | Biến môi trường và artifact paths | Cấu hình provider/model, đường dẫn và validation | Hoàn thành |
| Baseline orchestration | `src/pipelines/phase1.py` | Raw records hoặc Crossref response | Clean data, embeddings, index, metrics, quality/freshness report | Hoàn thành |
| Corruption/repair orchestration | `src/pipelines/corruption_flow.py` | Baseline artifacts, test set, raw snapshot | Corrupted/repaired datasets, metrics và comparison report | Hoàn thành |
| Integration tests | `tests/test_llm_config.py`, `tests/test_pipelines.py` | Các module đã được mock | Bằng chứng các flow dùng đúng contract và artifact | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Tích hợp sau khi merge | Cleaning, corruption, observability và evaluation | Thống nhất schema, key báo cáo và test set dùng chung |
| Hoàn thiện evaluation | LLM judge và Ragas | Ghi rõ provider/model, số lần thành công và fallback; báo cáo trung thực trạng thái Ragas |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Điều phối baseline end-to-end | `src/pipelines/phase1.py` | `data/results/baseline_metrics.json`, quality/freshness JSON và baseline report | Đối chiếu `data/reports/phase1_report.md` |
| Điều phối corruption và repair | `src/pipelines/corruption_flow.py` | Corrupted/repaired metrics và comparison report | Đối chiếu `data/reports/corruption_report.md` |
| Cấu hình Gemini/OpenAI | `src/retrieval/llm.py` | Gemini `gemini-3.5-flash-lite`, có provider validation | `tests/test_llm_config.py` và metrics artifacts |
| Giữ evaluation nhất quán | Pipeline integration | Cùng một test set 12 mẫu cho cả ba trạng thái | `data/eval/test_set.json` và answer artifacts |

Output quan trọng nhất của phần việc là một pipeline có thể nối toàn bộ module theo đúng thứ tự: raw ingestion → cleaning → embedding/index → evaluation → observability → corruption → repair → so sánh kết quả.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module được phát triển trên nhiều branch khác nhau nên cần một lớp orchestration thống nhất về schema, đường dẫn artifact, cấu hình provider và thứ tự chạy. Nếu tích hợp không đúng, pipeline có thể dùng test set khác nhau, repair bằng cách sao chép baseline, hoặc báo cáo metric không khớp artifact.

### Cách triển khai

Tôi tập trung cấu hình trong `Settings`, sau đó để `phase1.py` và `corruption_flow.py` chỉ điều phối các bước theo dependency rõ ràng. Baseline tạo hoặc tái sử dụng raw snapshot, chạy cleaning, build index, tạo test set, đánh giá và sinh observability artifacts. Corruption flow đọc lại baseline test set, tạo corrupted dataset, đánh giá, rồi repair bằng cách đọc `data/raw/crossref_records.json` và chạy cleaning lại.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | Crossref raw records, clean-data contract và biến môi trường |
| Output | Baseline/corrupted/repaired datasets, indexes, answers, metrics và reports |
| Module phụ thuộc | Ingestion, cleaning, embeddings, test set, evaluation, observability |
| Module sử dụng output | Reporting và phần phân tích kết quả cuối |
| Điều kiện lỗi cần xử lý | Thiếu API key, thiếu baseline artifact, sai schema hoặc test set không nhất quán |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Baseline và repaired đạt cùng mức metric; corrupted suy giảm rõ rệt.
- **Kết quả thực tế:** Baseline/repaired có retrieval hit rate `1.0`; corrupted còn `0.25`.
- **Artifact:** `data/results/`, `data/quality/`, `data/reports/`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định repair bằng cách nào để chứng minh khả năng phục hồi thực sự.
- **Các phương án đã cân nhắc:** Sao chép lại baseline clean CSV; hoặc đọc raw snapshot và chạy lại transformation.
- **Phương án đã chọn:** Đọc `data/raw/crossref_records.json`, chạy cleaning lại, rebuild index và re-evaluate.
- **Lý do:** Giữ đúng data lineage, reproducibility và tránh “repair giả”.
- **Bằng chứng:** Repaired dataset có 24 rows, pass 11/11 checks và các core metrics trở lại baseline.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Các module sau merge có khác biệt về clean schema, key báo cáo và cách truyền target document IDs.
- **Nguyên nhân gốc:** Các branch được phát triển song song với contract chưa đồng bộ hoàn toàn.
- **Cách xử lý:** Chốt clean contract 12 cột, dùng cùng test set, truyền `ground_truth_doc_ids` vào corruption và đồng bộ key giữa pipeline với reporting.
- **Cách xác minh:** Corrupted metrics giảm rõ rệt; repaired metrics và quality/freshness trở lại baseline.
- **Điều học được:** Integration cần được thiết kế dựa trên contract và artifact, không chỉ dựa vào việc từng module chạy riêng lẻ.

## 7. Hiểu biết về luồng end-to-end

Dữ liệu được lấy từ Crossref và lưu cả response gốc lẫn parsed raw records. Cleaning chuyển raw records thành clean DataFrame 12 cột. `text_for_embedding` được mã hóa bằng MiniLM và lưu vào ChromaDB. Test set chứa câu hỏi, ground truth và document IDs được dùng để đo retrieval hit rate và answer quality. Quality checks đánh giá tính đầy đủ, hợp lệ và trùng lặp; freshness tập trung vào độ mới theo ngày. Cả ba trạng thái phải dùng cùng test set để mọi thay đổi metric phản ánh thay đổi dữ liệu. Repair thành công khi repaired dataset được tái tạo từ raw snapshot, quality/freshness trở lại PASS và các metric quay lại baseline.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.2500 | 1.0000 | Corruption làm mất phần lớn document đúng; repair phục hồi hoàn toàn |
| `mean_token_f1` | 0.7500 | 0.0325 | 0.7500 | Nội dung câu trả lời suy giảm rất mạnh khi dữ liệu lỗi |
| `judge_accuracy` | 0.7500 | 0.0000 | 0.7500 | LLM judge xác nhận corrupted answers không đạt |
| `mean_judge_score` | 4 | 1 | 4 | Chất lượng câu trả lời giảm từ tốt xuống thấp nhất |
| Quality checks | PASS 11/11 | FAIL 8/11 | PASS 11/11 | Observability phát hiện đúng corruption |
| Freshness status | PASS | FAIL, stale ratio 0.3077 | PASS | Repair khôi phục độ mới dữ liệu |

Chuỗi nguyên nhân–bằng chứng:

1. Corruption nhắm vào evaluation documents → quality/freshness chuyển sang FAIL → retrieval và answer metrics giảm mạnh.
2. Repair từ raw snapshot → clean contract và freshness được phục hồi → core metrics trở lại đúng baseline.

## 9. Điều học được và hướng cải thiện

1. Orchestration cần kiểm soát artifact lineage và dependency giữa các bước.
2. Data observability phải được liên kết với model metrics để giải thích nguyên nhân suy giảm.
3. Một phép so sánh chỉ có ý nghĩa khi giữ cố định test set và cấu hình đánh giá.

Nếu có thêm thời gian, tôi sẽ bổ sung workflow tự động chạy baseline/corruption/repair và kiểm tra consistency giữa JSON artifacts với Markdown reports.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Vũ Văn Phong  
**Ngày xác nhận:** 2026-08-06
