# Báo cáo cá nhân — Đoàn Nhật Nam

## 1. Thông tin cá nhân

| Nội dung | Thông tin |
|---|---|
| Họ và tên | Đoàn Nhật Nam |
| MSSV | 2A202601123 |
| Branch phụ trách | `feat/observability-reports` |
| Phạm vi công việc | Data quality checks, freshness monitoring và sinh báo cáo |

## 2. Tổng quan bài lab

Bài lab xây dựng một pipeline dữ liệu có khả năng quan sát chất lượng ở nhiều trạng thái. Ngoài việc đánh giá retrieval và câu trả lời, hệ thống cần xác định dữ liệu có đầy đủ, hợp lệ, không trùng lặp và còn mới hay không. Phần observability cung cấp các kiểm tra này và chuyển kết quả thành JSON/Markdown reports dễ đọc.

## 3. Công việc được giao

Tôi phụ trách các module:

- `src/observability/quality.py`
- `src/observability/reporting.py`
- `tests/test_quality.py`
- `tests/test_reporting.py`

Các artifact liên quan nằm trong:

- `data/quality/`
- `data/reports/phase1_report.md`
- `data/reports/corruption_report.md`

## 4. Data quality checks

Tôi triển khai tập kiểm tra bao phủ những rủi ro quan trọng của clean dataset:

- Số lượng record tối thiểu.
- `paper_id` không null.
- `paper_id` duy nhất.
- Title không rỗng.
- Summary đạt độ dài tối thiểu.
- `text_for_embedding` không rỗng.
- Không có duplicate content.
- Published date hợp lệ.
- `age_days` hợp lệ.
- Tỷ lệ stale records.
- Ngày xuất bản mới nhất còn nằm trong freshness threshold.

Mỗi check ghi `success`, `observed`, `expected` và thông tin chi tiết. Báo cáo tổng hợp số check pass/fail và trạng thái overall để pipeline có thể phân biệt dữ liệu đạt yêu cầu hay không.

## 5. Freshness monitoring

Freshness report xác định ngày xuất bản mới nhất, cũ nhất, số record stale, stale ratio, số ngày không hợp lệ hoặc nằm trong tương lai và trạng thái tổng thể. Date được parse an toàn thay vì so sánh chuỗi trực tiếp.

Baseline sử dụng threshold 180 ngày. Dữ liệu sạch có stale ratio `0.0000`, trong khi corrupted dataset có stale ratio `0.3077`. Sau repair, stale ratio trở lại `0.0000`.

## 6. Báo cáo baseline

`phase1_report.md` tổng hợp:

- Metadata của lần chạy.
- Provider/model LLM.
- Embedding model và Chroma collection.
- Crossref query/filter.
- Raw và clean row counts.
- Clean schema.
- Evaluation metrics.
- LLM judge status.
- Ragas status.
- Data quality.
- Freshness.
- Agent demo và artifact paths.

Baseline cuối có 24 records và pass 11/11 quality checks. LLM judge chạy thành công 12/12 mẫu, không dùng heuristic fallback.

## 7. Báo cáo corruption và repair

`corruption_report.md` so sánh baseline, corrupted và repaired trên cùng một bảng. Báo cáo thể hiện delta của retrieval hit rate, token F1, judge accuracy và judge score, cùng với quality/freshness của cả ba trạng thái.

Kết quả chính:

| Trạng thái | Quality | Passed | Failed | Rows |
|---|---|---:|---:|---:|
| Baseline | PASS | 11 | 0 | 24 |
| Corrupted | FAIL | 8 | 3 | 26 |
| Repaired | PASS | 11 | 0 | 24 |

Kết luận trong báo cáo dựa trên số liệu thực tế: corruption làm giảm tất cả metric chính, còn repair từ raw snapshot khôi phục cả metrics, quality và freshness.

## 8. Kiểm thử

Tests kiểm tra clean dataset pass, corrupted dataset fail, freshness report được ghi đúng path, Markdown reports chứa đúng metrics và delta. Các test giúp phát hiện lỗi contract giữa pipeline và report generator, ví dụ khác nhau về tên key hoặc thiếu trường.

## 9. Khó khăn và cách xử lý

Khó khăn là thiết kế checks đủ nhạy để phát hiện corruption nhưng không làm baseline fail vì điều kiện quá cứng. Tôi sử dụng ngưỡng số record tối thiểu hợp lý, tách uniqueness khỏi duplicate-content detection và bổ sung date validation để invalid/future dates không bị coi là fresh.

Một vấn đề khác là báo cáo không được khẳng định hard-code rằng repair luôn đạt 100%. Kết luận được tạo dựa trên metrics thực tế để phản ánh trung thực kết quả chạy.

## 10. Kiến thức rút ra

Qua bài lab, tôi hiểu rõ hơn sự khác nhau giữa model evaluation và data observability. Một hệ thống có thể trả lời tốt ở thời điểm hiện tại nhưng vẫn cần kiểm tra chất lượng và freshness để phát hiện sớm rủi ro ở tầng dữ liệu.

## 11. Tự đánh giá

Tôi đã hoàn thành các quality/freshness checks và báo cáo so sánh ba trạng thái. Các checks đã phát hiện đúng corrupted data và xác nhận repaired data trở lại trạng thái baseline.