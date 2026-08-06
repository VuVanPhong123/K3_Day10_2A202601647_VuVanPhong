# Báo cáo cá nhân — Hoàng Lê Minh

## 1. Thông tin cá nhân

| Nội dung | Thông tin |
|---|---|
| Họ và tên | Hoàng Lê Minh |
| MSSV | 2A202601653 |
| Branch phụ trách | `feat/crossref-ingestion` |
| Phạm vi công việc | Xây dựng module lấy dữ liệu Crossref, parsing, retry/backoff và lưu raw artifacts |

## 2. Tổng quan bài lab

Bài lab xây dựng một pipeline dữ liệu cho hệ thống RAG dựa trên các bài báo khoa học lấy từ Crossref. Dữ liệu được tải về, lưu dưới dạng raw snapshot, làm sạch, tạo embedding, đưa vào ChromaDB và đánh giá ở ba trạng thái baseline, corrupted và repaired.

## 3. Công việc được giao

Tôi phụ trách tầng đầu tiên của pipeline: kết nối Crossref REST API và chuyển response thành cấu trúc dữ liệu nội bộ ổn định. Đây là phần nền tảng vì mọi bước cleaning, indexing, evaluation và repair đều phụ thuộc vào raw records được tạo ra từ module ingestion.

Các file và artifact chính liên quan gồm:

- `src/ingestion/crossref.py`
- `tests/test_crossref.py`
- `data/raw/crossref_response.json`
- `data/raw/crossref_records.json`

## 4. Các chức năng đã thực hiện

Tôi xây dựng dataclass `PaperRecord` để thống nhất các trường quan trọng như DOI, title, summary, authors, categories, published date, updated date, abstract URL và PDF URL.

Module gọi endpoint `https://api.crossref.org/works` với query, filter và số lượng bản ghi lấy từ cấu hình chung. Response gốc được lưu lại trước khi parse để phục vụ traceability và kiểm tra lại nguồn dữ liệu.

Phần parsing xử lý nhiều dạng dữ liệu Crossref không đồng nhất. Title có thể ở dạng danh sách, abstract có thể chứa HTML hoặc JATS tags, author có thể thiếu given name hoặc family name, ngày có thể nằm trong nhiều trường khác nhau. Tôi bổ sung logic làm sạch markup, normalize whitespace, ghép tên tác giả và chọn ngày phù hợp theo thứ tự ưu tiên.

Các record thiếu DOI, title hoặc abstract bị loại để tránh đưa dữ liệu không đủ điều kiện vào cleaning pipeline. Module cũng tìm PDF URL từ danh sách link khi content type hoặc phần mở rộng cho thấy đó là file PDF.

## 5. Retry, timeout và độ ổn định

Crossref là dịch vụ bên ngoài nên request có thể gặp lỗi tạm thời. Tôi triển khai timeout, danh sách retryable status code và exponential backoff. Các mã như 429, 500, 502, 503 và 504 được thử lại thay vì fail ngay. Nếu response có `Retry-After`, module ưu tiên dùng giá trị đó.

Cách xử lý này giúp pipeline ổn định hơn trước rate limit hoặc lỗi dịch vụ ngắn hạn, đồng thời vẫn raise lỗi rõ ràng khi vượt quá số lần thử.

## 6. Lưu và đọc raw snapshot

Tôi lưu hai artifact riêng:

- `crossref_response.json`: toàn bộ JSON response từ API.
- `crossref_records.json`: danh sách `PaperRecord` sau khi parse.

Tất cả file được ghi UTF-8 và giữ Unicode đầy đủ. Hàm `load_raw_records()` cho phép pipeline đọc lại snapshot mà không cần gọi Crossref mỗi lần.

Raw snapshot có vai trò đặc biệt trong repair flow. Khi dữ liệu clean bị corruption, hệ thống không sao chép baseline clean file mà đọc lại raw records rồi chạy cleaning từ đầu. Vì vậy phần ingestion vừa cung cấp dữ liệu đầu vào, vừa bảo đảm khả năng phục hồi và tái lập.

## 7. Kiểm thử và kết quả

Tests tập trung vào parsing payload, loại record không hợp lệ, làm sạch markup, parse author/date/link và hành vi retry. Module cũng được kiểm tra ở cấp tích hợp thông qua baseline pipeline.

Kết quả chạy thật thu được 24 raw records và 24 clean records. Các bản ghi này trở thành nền cho test set 12 câu hỏi, MiniLM embeddings, ChromaDB và toàn bộ đánh giá tiếp theo.

## 8. Khó khăn và cách xử lý

Khó khăn chính là dữ liệu Crossref có cấu trúc linh hoạt và không phải record nào cũng đầy đủ. Tôi xử lý bằng các hàm parse nhỏ, kiểm tra kiểu dữ liệu ở từng bước và dùng fallback hợp lý cho ngày, author và link. Với abstract chứa markup lỗi, parser vẫn cố gắng giữ phần text đã đọc được thay vì loại bỏ toàn bộ record.

## 9. Kiến thức rút ra

Qua phần việc này, tôi hiểu rõ hơn cách thiết kế ingestion module có khả năng chống lỗi, lưu raw data để audit và tách bước tải dữ liệu khỏi bước transformation. Tôi cũng nhận thấy raw snapshot là thành phần rất quan trọng trong data observability và recovery.

## 10. Tự đánh giá

Tôi đã hoàn thành module Crossref ingestion với đầy đủ parsing, retry/backoff, timeout và raw persistence. Phần việc đáp ứng đúng phạm vi branch và tích hợp thành công vào pipeline chung của nhóm.