# Báo cáo cá nhân — Nguyễn Quang Vinh

## 1. Thông tin cá nhân

| Nội dung | Thông tin |
|---|---|
| Họ và tên | Nguyễn Quang Vinh |
| MSSV | 2A202601517 |
| Branch phụ trách | `feat/cleaning-testset` |
| Phạm vi công việc | Làm sạch dữ liệu, xây dựng clean schema và tạo evaluation test set |

## 2. Tổng quan bài lab

Pipeline của nhóm lấy dữ liệu bài báo từ Crossref, chuyển raw records thành clean dataset, tạo embedding và đánh giá hệ thống RAG. Phần cleaning và test set là cầu nối giữa ingestion với indexing/evaluation, do đó cần có schema ổn định, kết quả deterministic và ground truth rõ ràng.

## 3. Công việc được giao

Tôi phụ trách hai module chính:

- `src/ingestion/cleaning.py`
- `src/evaluation/testset.py`

Các tests và artifact liên quan gồm:

- `tests/conftest.py`
- `tests/test_cleaning.py`
- `tests/test_testset.py`
- `data/clean/papers_clean.csv`
- `data/clean/papers_clean.json`
- `data/eval/test_set.json`

## 4. Làm sạch và chuẩn hóa dữ liệu

Tôi xây dựng clean DataFrame contract gồm 12 trường: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `updated`, `age_days`, `summary_chars`, `text_for_embedding`, `abs_url` và `pdf_url`.

Quy trình cleaning chuẩn hóa whitespace trong title và summary, loại phần tử rỗng trong authors/categories, loại trùng lặp không phân biệt hoa thường và ghép danh sách thành chuỗi phục vụ metadata. Các URL và paper ID cũng được chuẩn hóa thành chuỗi sạch.

Ngày xuất bản và cập nhật được parse về ISO date. `age_days` được tính dựa trên thời điểm chạy pipeline, còn `summary_chars` phản ánh đúng độ dài summary sau khi làm sạch. Trường `text_for_embedding` kết hợp title, summary, authors và categories để cung cấp ngữ cảnh đầy đủ hơn cho MiniLM.

Các record thiếu paper ID, title, summary hoặc embedding text bị loại. Dữ liệu được deduplicate theo paper ID và theo normalized title để tránh trường hợp nhiều document có tiêu đề giống nhau làm exact lookup trở nên mơ hồ. Kết quả cuối được sắp xếp deterministic theo published date và paper ID.

## 5. Xây dựng evaluation test set

Tôi tạo test set deterministic từ ba paper đầu tiên của clean dataset. Với mỗi paper, hệ thống sinh bốn loại câu hỏi:

1. Nội dung chính của bài báo.
2. Tác giả.
3. Ngày xuất bản.
4. Categories.

Mỗi mẫu có `id`, `question_type`, `question`, `ground_truth` và `ground_truth_doc_ids`. Câu hỏi trích dẫn đúng title để tương thích với exact lookup trong module QA. Ground truth được lấy từ chính các field mà pipeline dùng để trả lời, giúp việc đánh giá nhất quán.

Bộ test chính thức có 12 mẫu. Cùng một test set được sử dụng cho baseline, corrupted và repaired để bảo đảm phép so sánh công bằng.

## 6. Kiểm thử

Tests kiểm tra đầy đủ schema, dtype của DataFrame rỗng, filtering, deduplication, normalize whitespace, joined fields, date parsing, `age_days`, `summary_chars`, `text_for_embedding`, thứ tự deterministic và việc không mutate input records.

Tests của test set kiểm tra số lượng mẫu, bốn question types, ground truth, document IDs và tính deterministic. Module cũng raise lỗi rõ ràng khi clean corpus có ít hơn số document tối thiểu.

## 7. Kết quả đạt được

Pipeline thật tạo được 24 clean records từ 24 raw records. Clean dataset vượt qua 11/11 quality checks trong baseline. Bộ test 12 mẫu giúp hệ thống đo được retrieval hit rate, token F1, judge accuracy và judge score ở cả ba trạng thái.

Khi dữ liệu bị corruption, retrieval hit rate giảm từ `1.0` còn `0.25` và mean token F1 giảm từ `0.75` còn khoảng `0.0325`. Sau repair từ raw snapshot và chạy lại cleaning, các metric trở về baseline. Điều này cho thấy clean contract và test set đã hỗ trợ tốt cho việc đo tác động của data corruption.

## 8. Khó khăn và cách xử lý

Khó khăn chính là phải đồng bộ schema với index, QA và corruption modules. Tôi giải quyết bằng một danh sách cột contract cố định và thiết kế test bao phủ từng derived field. Với duplicate title, tôi lựa chọn loại bản ghi trùng vì exact lookup dựa trên title cần kết quả duy nhất.

## 9. Kiến thức rút ra

Qua bài lab, tôi hiểu rõ hơn vai trò của data contract, deterministic transformations và test-set design trong một pipeline đánh giá. Một bộ dữ liệu sạch không chỉ cần đúng schema mà còn phải phù hợp với downstream retrieval và observability.

## 10. Tự đánh giá

Tôi đã hoàn thành cleaning pipeline và evaluation test set theo đúng phạm vi được giao. Output tích hợp ổn định với embeddings, ChromaDB, evaluation và corruption/repair flow.