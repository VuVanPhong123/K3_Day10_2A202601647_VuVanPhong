# Báo cáo cá nhân — Vũ Văn Phong

## 1. Thông tin cá nhân

| Nội dung | Thông tin |
|---|---|
| Họ và tên | Vũ Văn Phong |
| MSSV | 2A202601647 |
| Branch phụ trách | `feat/pipeline-integration` |
| Phạm vi công việc | Tích hợp pipeline, cấu hình LLM, điều phối đánh giá và hoàn thiện luồng end-to-end |

## 2. Tổng quan bài lab

Bài lab xây dựng một pipeline dữ liệu hoàn chỉnh từ Crossref REST API, làm sạch dữ liệu bài báo, tạo embedding bằng `sentence-transformers/all-MiniLM-L6-v2`, lưu chỉ mục vào ChromaDB, tạo bộ câu hỏi đánh giá và so sánh ba trạng thái dữ liệu: baseline, corrupted và repaired. Hệ thống còn bổ sung các kiểm tra chất lượng dữ liệu, độ mới dữ liệu, LLM-as-a-judge và Ragas.

## 3. Công việc được giao

Tôi phụ trách ghép các module do các thành viên khác phát triển thành một quy trình có thể chạy xuyên suốt. Phạm vi chính gồm cấu hình provider LLM, baseline pipeline, corruption/repair pipeline, quản lý các đường dẫn artifact và integration tests.

Các file chính liên quan gồm:

- `src/core/config.py`
- `src/retrieval/llm.py`
- `src/pipelines/phase1.py`
- `src/pipelines/corruption_flow.py`
- `tests/test_llm_config.py`
- `tests/test_pipelines.py`
- `.env.example`
- `README.md`

## 4. Các chức năng đã thực hiện

Trong `config.py`, tôi chuẩn hóa cấu hình provider, model và toàn bộ đường dẫn đầu ra cho raw data, clean data, embeddings, test set, metrics, quality reports và comparison reports. Pipeline mặc định sử dụng Gemini với model `gemini-3.5-flash-lite`, đồng thời vẫn hỗ trợ OpenAI khi người dùng thay đổi `LLM_PROVIDER`.

Trong `llm.py`, tôi tích hợp cơ chế tạo LangChain chat model dựa trên provider được chọn và kiểm tra đúng API key tương ứng. Hệ thống không yêu cầu đồng thời cả Gemini key và OpenAI key. Với Gemini 3.x, cấu hình tránh truyền các sampling parameter không cần thiết.

Trong `phase1.py`, tôi điều phối luồng baseline theo thứ tự: tải hoặc tái sử dụng raw snapshot, gọi cleaning, lưu CSV/JSON, build MiniLM embeddings và Chroma collection, tạo hoặc tái sử dụng test set, chạy evaluation, chạy quality/freshness checks và sinh báo cáo. Pipeline cũng hỗ trợ agent demo khi bật biến môi trường.

Trong `corruption_flow.py`, tôi điều phối việc đọc baseline artifacts, tạo dữ liệu corrupted, build corrupted index, đánh giá bằng đúng test set baseline, sau đó repair bằng cách đọc lại raw snapshot và chạy cleaning. Cách repair này bảo đảm dữ liệu được phục hồi từ nguồn thô thay vì sao chép clean dataset ban đầu.

## 5. Kiểm thử và tích hợp

Tôi xây dựng integration tests bằng monkeypatch để kiểm tra pipeline mà không gọi API thật hoặc tải embedding model. Tests xác minh các hành vi quan trọng như tái sử dụng raw snapshot, refresh test set, dùng cùng test set cho cả ba trạng thái, lưu đúng artifact paths và repair từ raw records.

Sau khi merge các branch, tôi tiếp tục xử lý các lỗi contract giữa cleaning, corruption, reporting và evaluation. Phần tích hợp cuối bảo đảm LLM judge chạy thật, ghi rõ số lần thành công và fallback, đồng thời không âm thầm thay thế lỗi LLM bằng heuristic khi `REQUIRE_LLM_JUDGE=1`.

## 6. Kết quả đạt được

Kết quả baseline trên 12 mẫu đạt:

- Retrieval hit rate: `1.0`
- Mean token F1: `0.75`
- Judge accuracy: `0.75`
- Mean judge score: `4`
- LLM judge thành công: `12/12`
- Heuristic fallback: `0`

Sau corruption, retrieval hit rate giảm còn `0.25`, mean token F1 còn khoảng `0.0325`, judge accuracy còn `0.0` và mean judge score còn `1`. Sau repair, các metric quay lại đúng mức baseline. Điều này cho thấy pipeline tích hợp đã thể hiện rõ tác động của dữ liệu lỗi và khả năng phục hồi từ raw snapshot.

## 7. Khó khăn và cách xử lý

Khó khăn lớn nhất là các module được phát triển song song nên có thể khác nhau về schema, function signature và tên key trong báo cáo. Tôi xử lý bằng cách thống nhất contract dữ liệu, giữ một test set chung và dùng artifact paths tập trung trong `Settings`. Một vấn đề khác là Ragas và Gemini có thể tạo kết quả không ổn định với câu trả lời ngắn; phần tích hợp cuối đã bổ sung xử lý rõ ràng cho sample không đủ điều kiện và báo cáo trạng thái trung thực.

## 8. Kiến thức rút ra

Qua bài lab, tôi hiểu rõ hơn cách thiết kế pipeline có khả năng tái lập, cách tách cấu hình khỏi code, cách viết integration tests cho hệ thống nhiều dependency và cách duy trì data lineage từ raw data đến báo cáo cuối. Tôi cũng học được rằng repair pipeline chỉ có ý nghĩa khi thực sự quay lại nguồn dữ liệu thô và chạy lại transformation.

## 9. Tự đánh giá

Tôi đã hoàn thành phần tích hợp chính, bảo đảm các module hoạt động cùng nhau và tạo ra đầy đủ baseline, corrupted, repaired artifacts. Phần việc đáp ứng mục tiêu được giao và hỗ trợ nhóm chứng minh pipeline hoạt động end-to-end bằng số liệu thực tế.