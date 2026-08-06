# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Hoàng Lê Minh |
| MSSV | 2A202601653 |
| Khóa/Lớp | K3 |
| Tên nhóm | Nhóm Day 10 – Data Pipeline & Data Observability |
| Vai trò chính | Raw ingestion owner |
| Branch phụ trách | `feat/crossref-ingestion` |
| Repository | `VuVanPhong123/K3_Day10_2A202601647_VuVanPhong` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Crossref ingestion | `src/ingestion/crossref.py` | Query, filter và cấu hình request | Raw response và parsed `PaperRecord` | Hoàn thành |
| Retry/backoff | Request handling trong `crossref.py` | HTTP response và lỗi mạng | Request ổn định, lỗi rõ ràng khi hết retry | Hoàn thành |
| Raw persistence | Hàm lưu/đọc raw snapshot | Crossref JSON và parsed records | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |
| Unit tests | `tests/test_crossref.py` | Payload giả lập | Bằng chứng parsing và retry đúng | Hoàn thành |

## 3. Kết quả theo vai trò

Module ingestion lấy dữ liệu từ Crossref REST API, parse DOI, title, abstract, authors, subjects, ngày xuất bản/cập nhật và các URL liên quan. Kết quả chạy chính thức tạo 24 raw records, sau đó toàn bộ 24 record đi tiếp vào clean dataset.

Raw response được lưu nguyên trạng để audit, còn parsed raw records được lưu dưới dạng cấu trúc ổn định để pipeline có thể tái sử dụng mà không gọi API lại. Đây cũng là nguồn đáng tin cậy cho repair flow.

## 4. Giải thích phần kỹ thuật đã thực hiện

Crossref trả về dữ liệu không hoàn toàn đồng nhất: title thường là list, abstract có thể chứa HTML/JATS, author có thể thiếu given/family name và ngày có thể nằm ở nhiều trường. Tôi chia parsing thành các hàm nhỏ, kiểm tra kiểu dữ liệu và normalize whitespace trước khi tạo `PaperRecord`.

Request có timeout, retry cho các mã 429 và 5xx, exponential backoff và hỗ trợ `Retry-After`. Những record thiếu DOI, title hoặc abstract bị loại để tránh truyền dữ liệu không đủ điều kiện vào cleaning.

| Thành phần | Mô tả |
|---|---|
| Input | Crossref `/works` response |
| Output | Raw response JSON và danh sách `PaperRecord` |
| Module phụ thuộc | `requests`, cấu hình trong `Settings` |
| Module sử dụng output | Cleaning và repair pipeline |
| Điều kiện lỗi | Rate limit, timeout, malformed/thiếu trường |

```bash
uv run python script/run_phase1.py
```

Kết quả thực tế: 24 raw records được lưu và 24 clean records được tạo.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định chỉ lưu parsed records hay lưu cả response gốc.
- **Phương án:** Chỉ lưu dữ liệu đã parse; hoặc lưu cả raw response và parsed records.
- **Lựa chọn:** Lưu cả hai.
- **Lý do:** Response gốc phục vụ audit/debug, còn parsed records giúp pipeline và repair chạy ổn định.
- **Bằng chứng:** Repair đọc `data/raw/crossref_records.json` và khôi phục đầy đủ 24 records.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Crossref có thể trả 429/5xx hoặc abstract chứa markup làm dữ liệu khó dùng.
- **Nguyên nhân:** Rate limit/lỗi dịch vụ tạm thời và schema linh hoạt.
- **Cách xử lý:** Timeout, retry/backoff, xử lý `Retry-After`, làm sạch HTML/JATS và normalize text.
- **Xác minh:** Unit tests cho retry/parsing và baseline artifacts được tạo thành công.

## 7. Hiểu biết về luồng end-to-end

Crossref cung cấp raw response. Module của tôi chuyển response thành raw records có schema ổn định. Cleaning tạo clean dataset, MiniLM tạo embedding, ChromaDB lưu index, test set được dùng để đánh giá. Quality kiểm tra tính đầy đủ/hợp lệ, freshness kiểm tra độ mới. Corruption làm thay đổi dữ liệu có chủ đích; repair quay lại raw snapshot do module ingestion cung cấp rồi chạy lại transformation.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.2500 | 1.0000 | Raw snapshot đầy đủ cho phép repair phục hồi retrieval |
| `mean_token_f1` | 0.7500 | 0.0325 | 0.7500 | Corrupted corpus làm nội dung trả lời suy giảm |
| `judge_accuracy` | 0.7500 | 0.0000 | 0.7500 | Repaired data đưa kết quả về baseline |
| `mean_judge_score` | 4 | 1 | 4 | Chất lượng câu trả lời phục hồi sau repair |
| Quality checks | PASS 11/11 | FAIL 8/11 | PASS 11/11 | Raw source giúp tái tạo corpus sạch |
| Freshness | PASS | FAIL | PASS | Stale corruption được loại bỏ sau repair |

## 9. Điều học được và hướng cải thiện

Tôi học được cách thiết kế ingestion chịu lỗi, cách lưu raw snapshot để bảo đảm data lineage và tầm quan trọng của schema ổn định cho downstream modules. Nếu có thêm thời gian, tôi sẽ bổ sung validation chi tiết hơn cho các biến thể Crossref và cache theo query/filter.

## 10. Cam kết của thành viên

- [x] Báo cáo phản ánh đúng phần việc của tôi.
- [x] Tôi hiểu luồng end-to-end.
- [x] Các kết luận có artifact/metric đối chiếu.
- [x] Báo cáo không chứa secret.
- [x] Nội dung không sao chép nguyên báo cáo của thành viên khác.

**Họ và tên:** Hoàng Lê Minh  
**Ngày xác nhận:** 2026-08-06
