# Báo cáo vai trò thành viên — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Hoàng Lê Minh |
| MSSV | 2A202601653 |
| Khóa/Lớp | Cohort 3 |
| Tên nhóm | C5_2 |
| Vai trò chính | Role 1 — Crossref ingestion (Source owner) |
| Repository | `https://github.com/VuVanPhong123/K3_Day10_Data-Pipeline-Data-Observability` |
| Branch thực hiện | `feat/crossref-ingestion` |
| Commit chính | `a016784 feat: implement Crossref ingestion` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Parse Crossref payload | `src/ingestion/crossref.py`: `parse_crossref_payload()` | JSON response từ Crossref Works API | `list[PaperRecord]` đã map đủ metadata | Hoàn thành |
| Chuẩn hóa raw metadata | `_clean_markup()`, `_parse_authors()`, `_parse_categories()`, `_date_from_message()`, `_pdf_url()` | Các trường DOI, title, abstract, author, subject, date và link | Text bỏ HTML/JATS, tác giả/chủ đề dạng list, ngày ISO và URL | Hoàn thành |
| Crossref HTTP client | `fetch_source_records()`, `_request_crossref()` | `Settings`: query, filter, max results và artifact paths | Raw API response và raw records JSON | Hoàn thành |
| Khôi phục raw snapshot | `load_raw_records()` | `data/raw/crossref_records.json` | Danh sách `PaperRecord` dùng lại cho cleaning/repair | Hoàn thành |
| Kiểm thử ingestion | `tests/test_crossref.py`, `tests/fixtures/crossref_response.json` | Fixture Crossref offline và HTTP mock | 16 test cases cho parse, filtering, UTF-8, timeout và retry | Hoàn thành |

Phạm vi ownership chỉ gồm ba file được phân công trong `job.md`: `src/ingestion/crossref.py`, `tests/test_crossref.py` và `tests/fixtures/crossref_response.json`. Các module cleaning, evaluation, observability, corruption và orchestration do thành viên khác sở hữu.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xác minh contract raw → clean | Cleaning và pipeline integration | Baseline đọc được 24 raw records và tạo 24 clean records |
| Chạy kiểm thử tích hợp | Toàn bộ repository | 68 tests pass; có 2 cảnh báo parse ngày của pandas, không làm test fail |
| Tái hiện baseline và corruption/repair | Pipeline integration và observability | Sinh lại metrics, quality/freshness artifacts và comparison report thực tế |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse đủ metadata Crossref | `parse_crossref_payload()` | DOI, title, abstract, authors, subjects, published/updated, abstract URL và PDF URL | `test_parse_crossref_payload_extracts_all_required_fields_and_cleans_markup` |
| Làm sạch HTML/XML/JATS | `_MarkupTextExtractor`, `_clean_markup()` | Abstract/title dễ đọc, giữ Unicode và giải mã HTML entities | Fixture chứa JATS, `<i>`, `<p>`, `&amp;` và tiếng Việt |
| Loại raw record không hợp lệ | `parse_crossref_payload()` | Bỏ record thiếu DOI, title hoặc abstract | `test_parse_crossref_payload_handles_fallbacks_and_filters_invalid_records` |
| Gọi Crossref an toàn | `_request_crossref()` | Timeout 30 giây; exponential backoff; hỗ trợ `Retry-After` | Test cho `429`, `500`, `502`, `503`, `504` và lỗi `400` |
| Chặn retry vô hạn | `MAX_REQUEST_ATTEMPTS = 4` | Tối đa 4 request attempts | `test_fetch_stops_after_maximum_attempts` |
| Lưu và đọc raw artifact | `fetch_source_records()`, `load_raw_records()` | `crossref_response.json` và `crossref_records.json` UTF-8 | Test round-trip và kiểm tra Unicode trong file |

Output cụ thể của phần ingestion là:

- `data/raw/crossref_response.json`: snapshot JSON đầy đủ từ Crossref.
- `data/raw/crossref_records.json`: 24 records theo schema `PaperRecord`.
- Commit triển khai: `a016784` trên `feat/crossref-ingestion`, đã được merge vào `main` qua commit `4edab39`.
- Unit test Role 1: **16/16 pass**.

Lần chạy báo cáo dùng `REFRESH_SOURCE=0`, vì vậy pipeline đọc lại raw snapshot thay vì gọi lại nguồn sống. Cách này giữ corpus ổn định để baseline, corrupted và repaired có thể so sánh trên cùng dữ liệu.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref trả về metadata không đồng nhất: title thường là list, abstract có thể chứa HTML/JATS, tác giả có thể dùng `given`/`family` hoặc `name`, ngày có thể nằm trong nhiều trường và chỉ có năm/tháng, còn PDF phải tìm trong danh sách link. API công khai cũng có thể trả về lỗi tạm thời hoặc rate limit. Module ingestion phải biến dữ liệu này thành raw contract ổn định, có thể lưu lại và tái sử dụng mà không làm mất khả năng truy vết.

### Cách triển khai

1. Đọc `payload["message"]["items"]`; payload thiếu container hợp lệ trả về list rỗng.
2. Lấy và làm sạch DOI, title và abstract. Record thiếu một trong ba trường bắt buộc bị loại.
3. Dùng `HTMLParser` để bỏ HTML/JATS, giải mã character entities và giữ khoảng cách giữa các block text.
4. Ghép tên tác giả từ `given` và `family`, fallback sang `name`; subject được giữ thành list và phần tử đầu làm `primary_category`.
5. Parse `date-time` hoặc `date-parts` thành ISO date; nếu thiếu tháng/ngày thì dùng ngày đầu tiên của kỳ tương ứng.
6. Chọn URL DOI cho `abs_url` và link có content type/đuôi PDF cho `pdf_url`.
7. Gọi Crossref với timeout 30 giây. Các status `429`, `500`, `502`, `503`, `504` được retry tối đa 4 attempts bằng exponential backoff; `Retry-After` được ưu tiên nếu có.
8. Ghi raw response và `PaperRecord` bằng UTF-8, `ensure_ascii=False`; `load_raw_records()` kiểm tra JSON list và dựng lại dataclass.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref Works JSON; `source_query`, `source_filter`, `max_results` và paths từ `Settings` |
| Output | `list[PaperRecord]`, `data/raw/crossref_response.json`, `data/raw/crossref_records.json` |
| Raw schema | `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment` |
| Module phụ thuộc | `core.config.Settings`; thư viện `requests`; Python `HTMLParser` |
| Module sử dụng output | `src/ingestion/cleaning.py`, `src/pipelines/phase1.py`, repair flow |
| Điều kiện lỗi | Payload sai cấu trúc; record thiếu trường bắt buộc; ngày không hợp lệ; JSON snapshot sai schema; HTTP timeout/rate limit/server error |

### Cách xác minh

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe script\run_phase1.py
.\.venv\Scripts\python.exe script\run_corruption_flow.py
```

- **Kết quả mong đợi:** test pass; raw/clean/index/evaluation/quality artifacts tồn tại; corruption làm giảm ít nhất một quality hoặc RAG metric; repair quay lại gần baseline.
- **Kết quả thực tế:** 68 tests pass; baseline có 24 raw và 24 clean records; corrupted quality fail 3 checks và retrieval hit rate giảm từ 1.0 xuống 0.25; repaired trở lại baseline.
- **Artifact/log:** `data/raw/`, `data/results/*.json`, `data/quality/*.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.
- **Cấu hình đánh giá:** Gemini `gemini-3.5-flash-lite`, 12/12 LLM judgments thành công ở mỗi trạng thái; `RUN_RAGAS=0`, agent demo không được yêu cầu.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Abstract Crossref thường là fragment XML/JATS, có namespace tag, inline formatting và HTML entities.
- **Các phương án đã cân nhắc:** (1) dùng regex để xóa mọi chuỗi giống tag; (2) dùng `html.parser.HTMLParser` để đọc text theo cấu trúc.
- **Phương án đã chọn:** subclass `HTMLParser`, thu thập text node và chèn khoảng trắng ở các block tag phổ biến.
- **Lý do:** Regex ngắn hơn nhưng dễ nối hai đoạn văn, xử lý sai malformed markup và HTML entities. `HTMLParser` thuộc standard library, không thêm dependency, tự giải mã entities và chịu được HTML không hoàn chỉnh tốt hơn.
- **Bằng chứng quyết định phù hợp:** fixture chứa HTML, JATS namespace, inline tag, `&amp;` và Unicode; output chuẩn hóa đúng và toàn bộ 16 test Role 1 pass.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions` khi `SentenceTransformer` kiểm tra model `sentence-transformers/all-MiniLM-L6-v2` trên Hugging Face.
- **Lệnh tái hiện:** `.\.venv\Scripts\python.exe script\run_phase1.py` trong môi trường giới hạn network.
- **Nguyên nhân gốc:** embedding model chưa có đầy đủ trong local cache, trong khi sandbox chặn outbound socket đến Hugging Face. Đây không phải lỗi parsing hay raw schema.
- **Cách xử lý:** cho phép một lần tải model công khai, sau đó chạy lại pipeline bằng raw snapshot ổn định.
- **Cách xác minh sau khi sửa:** baseline hoàn thành với `Raw rows: 24`, `Clean rows: 24`; corruption flow sinh đủ corrupted/repaired metrics và comparison report.
- **Điều học được:** cần phân biệt lỗi dữ liệu/code với lỗi môi trường; model cache và network access phải được đưa vào checklist tái lập pipeline.

Ngoài ra, lần chạy `pytest` đầu tiên vượt quá 120 giây ở bước khởi động plugin. Chạy lại với `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` hoàn thành **68 tests trong 32.92 giây**, chứng minh nguyên nhân là overhead plugin chứ không phải test bị treo.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu từ Crossref đến vector index:** `fetch_source_records()` lấy response và lưu raw snapshot; `parse_crossref_payload()` chuyển item hợp lệ thành `PaperRecord`; cleaning chuẩn hóa và tạo `text_for_embedding`; MiniLM biến text thành vector; `LocalEmbeddingIndex` lưu vector cùng metadata trong collection Chroma tương ứng.
2. **Evaluation set và ground-truth IDs:** mỗi câu hỏi chứa đáp án chuẩn và `ground_truth_doc_ids`. Retrieval được tính hit khi danh sách tài liệu lấy về chứa ít nhất một ground-truth ID. Câu trả lời được so với ground truth bằng token F1 và LLM judge.
3. **Quality khác freshness:** quality kiểm tra cấu trúc/nội dung như row count, null, unique, summary length, embedding text và duplicate. Freshness tập trung vào thời gian: ngày hợp lệ, record quá cũ, stale ratio và ngày xuất bản mới nhất.
4. **Vì sao dùng cùng test set:** giữ biến đánh giá cố định. Khi metrics thay đổi, có thể quy nguyên nhân cho corpus bị corrupt hoặc được repair thay vì do câu hỏi/ground truth thay đổi.
5. **Khi nào repair thành công:** repaired dataset phải được dựng lại từ raw snapshot, quality/freshness phục hồi và metrics tiến gần hoặc trở lại baseline. Trong lần chạy này, repaired đạt đúng baseline ở bốn metrics chính, quality 11/11 và stale ratio 0.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.2500 | 1.0000 | Corruption làm giảm 0.75; repair phục hồi hoàn toàn |
| `mean_token_f1` | 0.7500 | 0.0325 | 0.7500 | Nội dung trả lời gần như mất overlap sau corruption |
| `judge_accuracy` | 0.7500 | 0.0000 | 0.7500 | LLM judge không chấp nhận câu trả lời corrupted nào |
| `mean_judge_score` | 4.0000 | 1.0000 | 4.0000 | Giảm 3 điểm rồi trở về baseline |
| Quality checks | 11/11 PASS | 8/11 PASS | 11/11 PASS | Corrupted fail summary length, duplicate và stale ratio |
| Freshness status | PASS, stale 0.0000 | FAIL, stale 0.3077 | PASS, stale 0.0000 | 8/26 corrupted rows bị stale; repair loại tác động |

Mỗi trạng thái dùng cùng 12 evaluation samples. Gemini `gemini-3.5-flash-lite` thực hiện thành công 12 judgments, không có heuristic fallback. Ragas được chủ động bỏ qua (`RUN_RAGAS=0`) để tránh thêm nhiều API calls.

### Kết luận từ số liệu

1. Drop tài liệu quan trọng kết hợp blank/noise summary, title truncation, stale date và duplicate → quality giảm từ 11/11 xuống 8/11, freshness chuyển PASS thành FAIL → `retrieval_hit_rate` giảm 1.00 xuống 0.25, `mean_token_f1` giảm 0.75 xuống 0.0325 và judge accuracy giảm xuống 0.
2. Repair đọc lại raw snapshot rồi chạy lại cleaning/indexing → quality và freshness trở lại PASS → cả bốn metrics chính trở lại đúng giá trị baseline.

Corruption ảnh hưởng trực tiếp nhất đến RAG nhiều khả năng là drop ground-truth document cùng với blank summary/title truncation trên các tài liệu evaluation, vì chúng làm mất tài liệu cần tìm hoặc phá hỏng tín hiệu truy hồi. Tuy nhiên flow hiện áp dụng nhiều scenario cùng lúc, nên số liệu chỉ chứng minh tác động tổng hợp; chưa đủ để quy một mức giảm riêng cho từng scenario. Muốn kết luận nhân quả riêng cần chạy ablation, mỗi lần chỉ bật một corruption.

Điểm khác kỳ vọng là check `latest_pub_date_fresh` vẫn PASS ở corrupted vì corpus vẫn còn một paper đủ mới (34 ngày), trong khi freshness tổng thể FAIL do 8/26 records stale (`stale_ratio=0.3077`). Điều này cho thấy chỉ nhìn ngày mới nhất là chưa đủ; stale ratio phát hiện vấn đề phân bố tốt hơn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw snapshot là điểm phục hồi quan trọng: ngoài khả năng audit, nó giúp tái chạy cleaning và repair mà không phụ thuộc Crossref thay đổi theo thời gian.
2. Data quality cần nhiều signal bổ sung nhau. Một record mới nhất vẫn có thể che giấu tỷ lệ lớn dữ liệu stale; uniqueness theo ID cũng chưa thay thế kiểm tra duplicate nội dung.
3. Chất lượng dữ liệu ảnh hưởng trực tiếp đến RAG: cùng model, index logic và test set nhưng corrupted corpus làm retrieval hit rate giảm 75 điểm phần trăm và LLM judge accuracy về 0.

### Nếu có thêm thời gian

Tôi sẽ bổ sung experiment ablation cho từng corruption scenario và báo cáo delta riêng. Cách đo là chạy cùng test set cho từng corpus chỉ có một loại lỗi, sau đó so sánh retrieval hit rate, token F1, quality/freshness signal và chi phí đánh giá. Việc này giúp xác định corruption nào gây tác động lớn nhất thay vì chỉ suy luận từ flow tổng hợp.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự đọc và xác nhận báo cáo:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hoàng Lê Minh

**Ngày xác nhận:** 2026-08-06
