# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Quang Vinh |
| MSSV | 2A202601517 |
| Khóa/Lớp | K3 |
| Vai trò chính | Cleaning & evaluation-set owner |
| Branch phụ trách | `feat/cleaning-testset` |
| Repository | `VuVanPhong123/K3_Day10_2A202601647_VuVanPhong` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output | Trạng thái |
|---|---|---|---|---|
| Cleaning/data model | `src/ingestion/cleaning.py` | Raw `PaperRecord` | Clean DataFrame/CSV/JSON | Hoàn thành |
| Evaluation set | `src/evaluation/testset.py` | Clean corpus | `data/eval/test_set.json` | Hoàn thành |
| Kiểm thử | `tests/test_cleaning.py`, `tests/test_testset.py` | Fixtures và edge cases | Bằng chứng contract/determinism | Hoàn thành |

## 3. Kết quả theo vai trò

Tôi xây dựng clean-data contract 12 cột: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `updated`, `age_days`, `summary_chars`, `text_for_embedding`, `abs_url`, `pdf_url`. Pipeline tạo 24 clean records từ 24 raw records.

Test set được tạo deterministic từ ba paper, mỗi paper có bốn loại câu hỏi: nội dung, tác giả, ngày xuất bản và categories. Tổng cộng có 12 mẫu, kèm ground truth và `ground_truth_doc_ids`.

## 4. Giải thích kỹ thuật

Cleaning chuẩn hóa whitespace, authors/categories, parse ngày về ISO, tính `age_days`, `summary_chars` và tạo `text_for_embedding`. Record thiếu ID/title/summary hoặc embedding text bị loại. Duplicate được xử lý theo paper ID và normalized title. Kết quả được sắp xếp deterministic.

Test set dùng chính các field trong clean corpus để tạo câu hỏi và đáp án. Cùng một test set được giữ nguyên cho baseline, corrupted và repaired để phép so sánh công bằng.

```bash
uv run python script/run_phase1.py
```

- **Kết quả thực tế:** 24 clean records, 12 evaluation samples và baseline pass 11/11 quality checks.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** Exact lookup dựa nhiều vào title nên duplicate title có thể làm ground truth không rõ ràng.
- **Phương án:** Giữ toàn bộ duplicate; hoặc deduplicate theo normalized title.
- **Lựa chọn:** Deduplicate theo paper ID và normalized title.
- **Lý do:** Giữ document identity ổn định và tránh nhiều kết quả cho cùng một câu hỏi.

## 6. Lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Schema và derived fields phải đồng bộ với embeddings, QA và corruption modules.
- **Nguyên nhân:** Nhiều module cùng phụ thuộc clean-data contract.
- **Cách xử lý:** Chốt danh sách cột cố định, viết test cho từng derived field và bảo đảm transformation không mutate input.
- **Xác minh:** Baseline/repaired cùng có 24 rows và core metrics giống nhau.

## 7. Hiểu biết về luồng end-to-end

Raw records từ Crossref được cleaning thành corpus có schema ổn định. `text_for_embedding` đi vào MiniLM/ChromaDB. Evaluation set cung cấp câu hỏi, ground truth và document IDs. Quality checks đánh giá completeness/validity/uniqueness, còn freshness đánh giá ngày dữ liệu. Giữ nguyên test set giúp đo đúng ảnh hưởng của corruption. Repair thành công khi chạy lại cleaning từ raw snapshot và metrics trở lại baseline.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.2500 | 1.0000 | Test set cố định cho thấy rõ ảnh hưởng dữ liệu |
| `mean_token_f1` | 0.7500 | 0.0325 | 0.7500 | Answer quality suy giảm mạnh khi corpus lỗi |
| `judge_accuracy` | 0.7500 | 0.0000 | 0.7500 | Repaired corpus phục hồi kết quả |
| `mean_judge_score` | 4 | 1 | 4 | Chất lượng quay về baseline |
| Quality | PASS 11/11 | FAIL 8/11 | PASS 11/11 | Clean contract được phục hồi |
| Freshness | PASS | FAIL | PASS | Stale corruption được loại bỏ |

## 9. Điều học được và hướng cải thiện

Tôi học được vai trò của data contract, deterministic transformation và evaluation-set design. Nếu có thêm thời gian, tôi sẽ mở rộng test set với nhiều document và question type hơn, đồng thời lưu hash của test set để xác minh chính xác tính nhất quán giữa các lần chạy.

## 10. Cam kết

- [x] Báo cáo đúng phần việc.
- [x] Tôi hiểu luồng end-to-end.
- [x] Kết luận có artifact/metric.
- [x] Không chứa secret.

**Họ và tên:** Nguyễn Quang Vinh  
**Ngày xác nhận:** 2026-08-06
