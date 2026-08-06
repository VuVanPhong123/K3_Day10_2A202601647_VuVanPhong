# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Đoàn Nhật Nam             |
| MSSV               | 2A202601123               |
| Khóa/Lớp         | K3                        |
| Tên nhóm         | C502                       |
| Vai trò chính    | Data observability và reports |
| Repository         | feat/observability-reports |
| Ngày hoàn thành | 2026-08-06                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Quality Checks | `src/observability/quality.py` (`run_data_quality_checks`) | `df`, `settings` | `data/quality/{report_name}.json` | Hoàn thành |
| Freshness Monitoring | `src/observability/quality.py` (`build_freshness_report`) | `df`, `settings` | `data/quality/freshness_report.json` | Hoàn thành |
| Phase 1 Report | `src/observability/reporting.py` (`generate_phase1_report`) | `source_summary`, `metrics`, `quality`, `freshness` | `data/reports/phase1_report.md` | Hoàn thành |
| Corruption Comparison Report | `src/observability/reporting.py` (`generate_corruption_report`) | Metrics/Quality/Freshness của 3 trạng thái | `data/reports/corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Viết Unit Tests tự động | Module `quality.py` và `reporting.py` | Tạo `tests/test_quality.py` và `tests/test_reporting.py` giúp nhóm verify code nhanh chóng. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Cài đặt 9 bộ kiểm tra chất lượng dữ liệu | `src/observability/quality.py` | `data/quality/baseline_quality.json` | `python -m pytest tests/test_quality.py` |
| Tính toán chỉ số tươi mới của dữ liệu | `src/observability/quality.py` | `data/quality/freshness_report.json` | Kiểm tra trường `is_fresh` và `stale_ratio` trong JSON |
| Xuất báo cáo Markdown cho Phase 1 | `src/observability/reporting.py` | `data/reports/phase1_report.md` | Mở file kiểm tra bảng chỉ số và status |
| Xuất báo cáo so sánh Delta 3 trạng thái | `src/observability/reporting.py` | `data/reports/corruption_report.md` | Kiểm tra bảng so sánh Absolute & Delta |

**Artifact cụ thể đã tạo ra:** 
Báo cáo so sánh `data/reports/corruption_report.md` tự động tính toán mức giảm của RAG Agent khi dữ liệu bị lỗi (Hit Rate giảm từ 0.9167 xuống 0.4167, delta `-0.5000`) và khả năng phục hồi 100% sau khi Repair.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Hệ thống RAG dễ bị giảm độ chính xác nếu dữ liệu đầu vào bị hỏng (trùng lặp, thiếu thông tin, bị rác hoặc quá cũ). Cần một bộ công cụ tự động kiểm tra chất lượng dữ liệu (Data Quality Checks & Freshness Monitoring) và sinh báo cáo so sánh trực quan (Markdown Report) để đo lường tác động của dữ liệu xấu lên Agent.

### Cách triển khai
- **Data Quality**: Duyệt DataFrame bằng Pandas kiểm tra 9 tiêu chí cố định (`paper_id` not null & unique, `title` không rỗng, `summary_chars` >= 100, `text_for_embedding` không rỗng, không duplicate, `stale_records_ratio` == 0). Kết quả trả về cấu trúc chuẩn dict gồm `name`, `success`, `observed`, `expected`, `details`.
- **Freshness**: So sánh `published` date với `freshness_threshold_days` (180 ngày) để tính `stale_rows` và trạng thái `is_fresh`.
- **Reporting**: Dùng string formatting để tự động tổng hợp số liệu thành các bảng Markdown chuẩn, tính toán chênh lệch (Delta = Current - Baseline) cho từng metric.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ------ |
| Input | `pd.DataFrame` (chứa dữ liệu bài báo), `Settings` (cấu hình ngưỡng và đường dẫn) |
| Output | Dict kết quả quality/freshness, file JSON tại `data/quality/`, file Markdown tại `data/reports/` |
| Module phụ thuộc | `core.config`, `core.utils` |
| Module sử dụng output | `pipelines/phase1.py`, `pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | DataFrame rỗng, thiếu cột `published` hoặc `paper_id` |

### Cách xác minh

```bash
PYTHONPATH=src python -m pytest tests/test_quality.py tests/test_reporting.py
```

- **Kết quả mong đợi:** Tất cả test cases trong `test_quality.py` và `test_reporting.py` chạy qua 100%.
- **Kết quả thực tế:** `ALL OBSERVABILITY TESTS PASSED!`.
- **Artifact/log:** `data/quality/baseline_quality.json`, `data/reports/phase1_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn công cụ cho Data Quality Checks giữa Pandas thuần và Great Expectations (GX).
- **Các phương án đã cân nhắc:**
  1. Dùng Great Expectations (GX): Cung cấp suite mạnh mẽ nhưng setup cồng kềnh, sinh nhiều file cấu hình phụ thuộc.
  2. Dùng Pandas checks thuần: Tự viết hàm kiểm tra trên DataFrame.
- **Phương án đã chọn:** Dùng Pandas checks thuần cho phase đầu.
- **Lý do:** Giúp pipeline chạy cực nhanh, nhẹ, không bị rủi ro lỗi phiên bản thư viện và dễ xuất JSON payload đúng schema yêu cầu.
- **Bằng chứng:** Thời gian thực thi bộ checks < 0.1s, kết quả xuất ra dạng JSON nhất quán.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi:** `FileNotFoundError: [Errno 2] No such file or directory: 'data/clean/papers_clean.json'` khi chạy test độc lập module reporting.
- **Lệnh tái hiện:** `python script/test_reporting_runner.py`
- **Nguyên nhân gốc:** Module reporting chạy trước khi pipeline cleaning tạo ra file `papers_clean.json`.
- **Cách xử lý:** Trong script runner, thêm logic kiểm tra file tồn tại; nếu chưa có thì tự động gọi `load_raw_records` và `build_clean_dataframe` để khởi tạo dữ liệu tạm.
- **Cách xác minh sau khi sửa:** Chạy lại script runner trả về `Generated phase 1 report at: data/reports/phase1_report.md` thành công code 0.
- **Bài học:** Các script test/runner độc lập luôn cần có cơ chế fallback hoặc kiểm tra tính sẵn sàng của artifacts đầu vào.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index:** 
   Crossref REST API -> Payload JSON thô -> Parse & Clean (loại rác, chuẩn hóa text, tính age_days) -> DataFrame sạch -> Sinh `text_for_embedding` -> Sentence-Transformers (`all-MiniLM-L6-v2`) tạo vector -> Lưu vào ChromaDB vector store.

2. **Evaluation set và ground-truth document IDs:**
   Evaluation set gồm các câu hỏi cố định kèm `ground_truth` và `ground_truth_doc_ids`. Khi Agent trả lời, hệ thống so sánh câu trả lời với `ground_truth` (tính Token F1, LLM Judge Score) và kiểm tra xem tài liệu retrieved có chứa ID trong `ground_truth_doc_ids` hay không (tính Retrieval Hit Rate).

3. **Quality checks khác Freshness monitoring ở điểm nào:**
   Quality checks tập trung vào tính toàn vẹn của dữ liệu (null, duplicate, độ dài text, tính duy nhất của ID). Freshness monitoring tập trung vào mốc thời gian (ngày xuất bản bài báo có bị cũ quá ngưỡng cho phép hay không).

4. **Vì sao phải dùng cùng test set cho 3 trạng thái:**
   Để đảm bảo tính công bằng và nhất quán (apples-to-apples comparison). Chỉ khi giữ nguyên bộ câu hỏi thử nghiệm, ta mới đo lường chính xác được độ suy giảm performance do data corruption gây ra.

5. **Repair được xem là thành công khi nào:**
   Khi các Quality checks quay lại trạng thái `PASSED` (9/9 checks), Freshness chuyển về `FRESH`, và các chỉ số RAG (Hit Rate, F1, Judge Score) phục hồi về tiệm cận hoặc bằng mức Baseline ban đầu.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate`   |   0.9167 |    0.4167 |   0.9167 | Dữ liệu lỗi làm Hit Rate giảm mạnh 50%. Repair giúp phục hồi 100%. |
| `mean_token_f1`        |   0.8523 |    0.3850 |   0.8523 | Token F1 giảm hơn 0.46 khi text bị xáo trộn/truncate. |
| `judge_accuracy`       |   0.9167 |    0.4167 |   0.9167 | Độ chính xác câu trả lời tỷ lệ thuận với chất lượng retrieval. |
| `mean_judge_score`     |   4.5833 |    2.1500 |   4.5833 | Điểm đánh giá của LLM Judge rớt từ 4.58 xuống 2.15 do nhiễu dữ liệu. |
| Quality checks         | 9/9 Pass | 5/9 Pass  | 9/9 Pass | Đã phát hiện đúng 4 lỗi bị inject vào dữ liệu. |
| Freshness status       |    FRESH |     STALE |    FRESH | Đã phát hiện dữ liệu bị ép lùi ngày xuất bản về quá cũ. |

### Kết luận từ số liệu

1. **[Data corruption (truncate title, blank summary, stale date)]** → **[Quality fail 4 checks, Freshness báo Stale]** → **[Hit rate rớt 50%, LLM Judge Score rớt từ 4.58 xuống 2.15]**.
2. **[Repair action (re-ingest w& clean từ nguồn chuẩn Crossref)]** → **[Quality & Freshness đạt 100% Pass]** → **[Metrics của Agent phục hồi 100% về mức Baseline]**.

- **Corruption ảnh hưởng rõ nhất:** Việc xóa/blank `summary` và xáo trộn `title` làm suy giảm nặng nhất vì vector search không còn thông tin ngữ nghĩa đúng để match context.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. Dữ liệu đầu vào quyết định trực tiếp tới chất lượng hệ thống RAG (Garbage in, Garbage out).
2. Data Observability là lớp phòng thủ chủ động giúp phát hiện sự cố dữ liệu trước khi làm hỏng kết quả của LLM Agent.
3. Việc tự động hóa đo lường Delta giữa các phiên bản pipeline giúp kiểm chứng chính xác hiệu quả của việc sửa lỗi.

### Nếu có thêm thời gian
Tôi sẽ tích hợp thêm công cụ gửi cảnh báo tự động qua Slack/Email Webhook mỗi khi Data Quality Check bị FAILED hoặc Freshness báo STALE.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đoàn Nhật Nam  
**Ngày xác nhận:** 2026-08-06
