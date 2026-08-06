# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Đoàn Nhật Nam |
| MSSV | 2A202601123 |
| Khóa/Lớp | K3 |
| Vai trò chính | Observability & reporting owner |
| Branch phụ trách | `feat/observability-reports` |
| Repository | `VuVanPhong123/K3_Day10_2A202601647_VuVanPhong` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output | Trạng thái |
|---|---|---|---|---|
| Data quality/freshness | `src/observability/quality.py` | Clean/corrupted/repaired DataFrame | Quality và freshness JSON | Hoàn thành |
| Reporting | `src/observability/reporting.py` | Metrics và observability artifacts | Baseline/comparison Markdown reports | Hoàn thành |
| Kiểm thử | `tests/test_quality.py`, `tests/test_reporting.py` | Fixtures và metrics giả lập | Bằng chứng checks/report đúng contract | Hoàn thành |

## 3. Kết quả theo vai trò

Tôi xây dựng các checks cho row count, null/unique paper ID, title/summary/embedding text, duplicate content, published date, `age_days`, stale ratio và ngày mới nhất. Baseline và repaired pass 11/11 checks; corrupted chỉ pass 8/11.

Freshness report cho thấy baseline/repaired có stale ratio `0.0000`, còn corrupted tăng lên `0.3077`. Reporting module tổng hợp các metric và delta vào `data/reports/phase1_report.md` và `data/reports/corruption_report.md`.

## 4. Giải thích kỹ thuật

Mỗi quality check trả về trạng thái, observed value, expected value và details. Overall status chỉ PASS khi toàn bộ điều kiện bắt buộc đạt. Freshness parse ngày an toàn, tính ngày mới nhất/cũ nhất, invalid/future dates và stale ratio.

| Thành phần | Mô tả |
|---|---|
| Input | DataFrame và evaluation metrics |
| Output | JSON quality/freshness và Markdown report |
| Module sử dụng output | Pipeline orchestration và báo cáo cuối |
| Điều kiện lỗi | Thiếu cột, ngày không hợp lệ, duplicate hoặc stale data |

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** Báo cáo không được hard-code rằng repair luôn thành công.
- **Phương án:** Viết kết luận cố định; hoặc sinh kết luận từ artifact hiện tại.
- **Lựa chọn:** Dựa vào metrics, quality và freshness thực tế.
- **Lý do:** Bảo đảm báo cáo trung thực, tái sử dụng được cho các lần chạy khác.
- **Bằng chứng:** Comparison report phản ánh đúng PASS → FAIL → PASS và delta của từng metric.

## 6. Lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Baseline cần pass nhưng checks vẫn phải đủ nhạy để phát hiện corruption.
- **Nguyên nhân:** Threshold quá cứng có thể làm dữ liệu hợp lệ fail; quá lỏng sẽ bỏ sót lỗi.
- **Cách xử lý:** Tách completeness, uniqueness, duplicate-content và freshness; dùng threshold phù hợp với corpus.
- **Xác minh:** Baseline/repaired pass 11/11, corrupted fail 3 checks và freshness FAIL.

## 7. Hiểu biết về luồng end-to-end

Dữ liệu đi từ Crossref raw records qua cleaning, embeddings/ChromaDB và evaluation. Quality checks trả lời dữ liệu có đủ, hợp lệ, duy nhất hay không; freshness trả lời dữ liệu có còn mới hay không. Corruption làm thay đổi cả tín hiệu dữ liệu lẫn agent metrics. Repair được xác minh khi quality/freshness và core metrics quay lại baseline trên cùng test set.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.2500 | 1.0000 | Giảm đồng thời với quality FAIL |
| `mean_token_f1` | 0.7500 | 0.0325 | 0.7500 | Nội dung corrupted làm answer suy giảm |
| `judge_accuracy` | 0.7500 | 0.0000 | 0.7500 | LLM judge xác nhận khác biệt |
| `mean_judge_score` | 4 | 1 | 4 | Repair phục hồi chất lượng |
| Quality | PASS 11/11 | FAIL 8/11 | PASS 11/11 | Checks phát hiện đúng trạng thái |
| Freshness | PASS | FAIL, 0.3077 | PASS | Stale-date corruption được nhận diện |

## 9. Điều học được và hướng cải thiện

Tôi học được sự khác nhau giữa model evaluation và data observability, cách thiết kế signals giải thích được và cách sinh báo cáo dựa trên evidence. Nếu có thêm thời gian, tôi sẽ thêm trend history giữa nhiều lần chạy và cảnh báo tự động khi metric/quality vượt ngưỡng.

## 10. Cam kết

- [x] Báo cáo đúng phần việc.
- [x] Tôi hiểu luồng end-to-end.
- [x] Kết luận có artifact/metric.
- [x] Không chứa secret.

**Họ và tên:** Đoàn Nhật Nam  
**Ngày xác nhận:** 2026-08-06
