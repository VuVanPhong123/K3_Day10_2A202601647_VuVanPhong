# Member Role Report — Day 10: Data Pipeline & Data Observability

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Quang Vinh       |
| MSSV               | 2A202601517                |
| Khóa/Lớp         | K3                        |
| Tên nhóm         | Team Data Pipeline        |
| Vai trò chính    | Người 2 — Cleaning & Test Set |
| Repository         | https://github.com/VuVanPhong123/K3_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Data cleaning pipeline | `src/ingestion/cleaning.py`: `build_clean_dataframe()` | list[PaperRecord], run_date | pd.DataFrame (12 cột contract) | Hoàn thành |
| Evaluation test set builder | `src/evaluation/testset.py`: `build_test_set()` | pd.DataFrame (cleaned), output_path | list[dict] with 12 samples (4 types × 3 papers) | Hoàn thành |
| Test fixtures & test cases | `tests/conftest.py`, `tests/test_cleaning.py`, `tests/test_testset.py` | Fixtures (7 PaperRecord), df | 28 passing unit tests | Hoàn thành |

Chỉ nhận ownership cho phần bạn trực tiếp thực hiện. Liên hệ rõ phần việc của bạn với đầu vào, đầu ra và các thành viên phụ thuộc vào phần đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Tư vấn dedupe title và exact lookup | Người 3 (Observability), Người 4 (Corruption) | Chốt quy định: duplicate titles phải loại bỏ vì `index.documents_by_title` là dict; `ground_truth_doc_ids` của test set phải khớp với doc bị tác động khi corruption |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Chuẩn hóa và làm sạch raw records từ Crossref | `src/ingestion/cleaning.py` | 12-column DataFrame: paper_id, title, summary, authors_joined, categories_joined, published (ISO), updated (ISO), age_days, summary_chars, text_for_embedding, abs_url, pdf_url | `pytest tests/test_cleaning.py -v` → 16/16 pass |
| Xây dựng deterministic evaluation test set | `src/evaluation/testset.py` | JSON file với 12 samples (q01_summary, q01_authors, q01_date, q01_categories, q02_*, q03_*) mỗi mẫu có id, question_type, question (với exact title trong '...'), ground_truth, ground_truth_doc_ids | `pytest tests/test_testset.py -v` → 12/12 pass |
| Phát triển test fixtures và test suite | `tests/conftest.py`, `tests/test_cleaning.py`, `tests/test_testset.py` | 7 synthetic PaperRecord fixtures, 16 cleaning tests, 12 testset tests (28 total) | `pytest tests/test_*.py` → 28 pass |

**Output cụ thể:**

Cleanup pipeline tạo ra DataFrame sạch với 12 cột contract đảm bảo:
- Không có null/empty title, summary, text_for_embedding
- Title/authors/categories chuẩn hóa (whitespace, dedup case-insensitive)
- published/updated là ISO date string (sentinel: ""), age_days ≥ -1
- Dedupe theo paper_id và title đã normalize (vì qa.py dùng `index.documents_by_title`)
- Sort deterministic: published giảm dần, paper_id tăng dần

Test set emits 12 mẫu cố định từ 3 paper đầu, phân 4 loại câu hỏi. Câu hỏi khớp routing keyword của `qa._extract_answer` và luôn quote exact title để `index.lookup` thành công. Ground truth lấy từ exact field (summary.first_sentence, authors_joined, published, categories_joined) nên metrics có thể đối chiếu chính xác.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Raw records từ Crossref có:
- Whitespace thừa, title/summary không chuẩn hóa
- Authors/categories có thể trùng lặp hoặc rỗng
- Date format không nhất quán, có thể missing
- Duplicate papers (cùng title hoặc paper_id)
- Không có embedding text unified

→ Cần cleaning pipeline **deterministic** để tạo DataFrame sạch sẽ phục vụ embedding và evaluation mà không phụ thuộc thứ tự input.

Evaluation test set cần:
- Từ cleaned DataFrame, chọn **cố định** một tập papers để kiểm tra retrieval
- Câu hỏi phải khớp logic router của `qa._extract_answer` (keyword routing)
- Ground truth phải lấy từ đúng field mà agent sẽ trả lời
- Test set dùng lại cho baseline/corrupted/repaired để đo impact

### Cách triển khai

**Cleaning:**
1. Normalize whitespace trong title, summary
2. Dedupe authors/categories case-insensitively
3. Parse published/updated thành ISO date string; unparseable → ""
4. Compute age_days = (run_date - published).days; missing → -1
5. Build text_for_embedding từ title + summary + authors_joined + categories_joined
6. Drop rows: empty paper_id, title, summary, hoặc text_for_embedding
7. **Dedupe theo paper_id (keep first) AND theo title_key (keep first)** — vì `index.documents_by_title` là dict
8. Sort: published desc, paper_id asc (đảm bảo deterministic bất kể input order)

**Test set builder:**
1. Check corpus ≥ 3 documents
2. Select first 3 papers (đã sort)
3. Sinh 12 samples: mỗi paper × 4 question type
4. Question templates khớp keyword routing: "who authored '...'", "when was ... published", "what categories ... '...'", "what is ... about"
5. Ground truth từ exact field match: summary→first_sentence, authors→authors_joined, date→published, categories→categories_joined

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input (cleaning)               | list[PaperRecord] (từ crossref.py), run_date: datetime          |
| Output (cleaning)              | pd.DataFrame: 12 cột (paper_id, title, summary, authors_joined, categories_joined, published [ISO], updated [ISO], age_days [int], summary_chars [int], text_for_embedding, abs_url, pdf_url) |
| Input (testset)                | pd.DataFrame (cleaned), output_path: Path |
| Output (testset)               | list[dict] × 12 (id, question_type, question, ground_truth, ground_truth_doc_ids); ghi JSON |
| Module phụ thuộc               | `core.utils` (normalize_whitespace, compact_join, first_sentence, write_json) |
| Module sử dụng output          | `retrieval.index` (build từ DataFrame), `evaluation.metrics` (evaluate từ test_set JSON), `pipelines.phase1` (orchestrate) |
| Điều kiện lỗi cần xử lý        | Empty input → empty DataFrame với đúng cột; invalid date → age_days=-1, published=""; corpus < 3 papers → ValueError |

### Cách xác minh

```bash
cd "d:\vin_labs\lab10\K3_Day10_Data-Pipeline-Data-Observability"
.venv\Scripts\python.exe -m pytest tests/test_cleaning.py tests/test_testset.py -v
```

- **Kết quả mong đợi:** 28 tests pass (16 cleaning + 12 testset)
- **Kết quả thực tế:** 28 passed in 19.34s
- **Artifact/log:** Branch `feat/cleaning-testset`, commits `8a69610`, `3f9dd8c`, merge `1b63e7f`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Deduplicate records khi có trùng lặp title hoặc paper_id. Spec ban đầu chỉ nói dedupe theo paper_id, nhưng `qa.py` dùng `index.documents_by_title` (dict) để exact lookup theo title — nếu hai docs cùng title, dict sẽ ghi đè và retrieval không xác định.

- **Các phương án đã cân nhắc:** 
  1. Chỉ dedupe paper_id (theo spec gốc)
  2. Dedupe paper_id AND title đã normalize (đảm bảo exact lookup work)

- **Phương án đã chọn:** Dedupe theo **cả paper_id và title_key** (title lowercase), giữ record đầu tiên trong input order.

- **Lý do:** 
  - **Correctness**: Nếu hai docs cùng title, exact lookup sẽ trả về doc tùy ý (dict last-write-wins). Test set câu hỏi quote exact title, nên retrieval phải deterministic → cần loại duplicate title.
  - **Data quality**: Duplicate title thường là lỗi ingestion, phải loại.
  - **Impact**: Nếu không dedupe title, test set metrics sẽ không consistent vì ground_truth_doc_id có thể không khớp retrieved doc.
  - **Reproducibility**: Sort trước khi dedupe (input order) hay dedupe trước sort? Chọn dedupe theo thứ tự input (keep first), rồi sort → đảm bảo deterministic + keep first logic logic rõ ràng.

- **Bằng chứng quyết định phù hợp:** 
  - Test `test_drops_duplicate_title` xác minh: nếu fixture có 2 records cùng title → output chỉ giữ 1
  - Test `test_question_quotes_exact_title` + `test_ground_truth_matches_source_row` xác minh: question quote title → ground_truth lấy từ matching row (duy nhất) → metrics align
  - 16/16 cleaning tests pass, không break downstream (testset tests cũng 12/12 pass)

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** 
  ```
  FAILED tests/test_cleaning.py::test_drops_duplicate_title - AssertionError: 
  assert 'doi_2024_005' not in {'doi_2024_002', 'doi_2024_003', 'doi_2024_004', 'doi_2024_005'}
  ```
  Test fixture có doi_2024_005 (trùng title với doi_2024_001 nhưng published date mới hơn 1 ngày) — test kỳ vọng nó bị loại, nhưng kết quả nó vẫn trong output.

- **Lệnh hoặc bước tái hiện:** 
  ```bash
  pytest tests/test_cleaning.py::test_drops_duplicate_title -v
  ```

- **Nguyên nhân gốc:** 
  Tôi đã sort DataFrame **trước** khi dedupe theo title. Sort sắp xếp theo published DESC, nên 005 (2024-01-16) lên trên 001 (2024-01-15). Khi dedupe với `keep="first"`, nó giữ 005 (bây giờ là hàng đầu) thay vì 001 (record gốc đầu tiên).
  
  Logic đúng: "keep first" nghĩa là keep first occurrence **trong input** chứ không phải sau sort.

- **Cách xử lý:** 
  Reorder dedupe: 
  ```python
  # BEFORE (sai): sort → dedupe (keep first sai)
  df = df.sort_values(...)[...]
  df = df.drop_duplicates(..., keep="first")
  
  # AFTER (đúng): dedupe → sort
  df = df.drop_duplicates(..., keep="first")  # Keep first from input
  df = df.sort_values(...)[...]  # Then sort
  ```

- **Cách xác minh sau khi sửa:** 
  ```bash
  pytest tests/test_cleaning.py::test_drops_duplicate_title -v
  pytest tests/test_cleaning.py -v  # All 16 pass
  pytest tests/test_testset.py -v   # All 12 pass
  ```
  Kết quả: PASSED

- **Điều học được:** 
  - Khi dedupe có "keep first", phải hiểu rõ "first" là first **trong original input** hay first **sau transformation**. 
  - Thứ tự operation quan trọng: sort → dedupe vs. dedupe → sort cho kết quả khác.
  - Viết test trước (TDD) sẽ catch lỗi này ngay vì test set fixture đã định nghĩa hành vi mong đợi.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   - Crossref API trả `items[]` (raw), `parse_crossref_payload()` extract DOI/title/abstract/authors/dates → PaperRecord
   - `build_clean_dataframe()` (phần tôi làm) chuẩn hóa, xóa rác, tạo text_for_embedding
   - `LocalEmbeddingIndex.build()` chạy `MiniLMEmbeddings` encode text_for_embedding thành vectors
   - ChromaDB lưu vectors + metadata (title, published, authors_joined, categories_joined) → ready cho search

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   - Test set (phần tôi làm) define 12 câu hỏi (4 loại), mỗi câu assign ground_truth_doc_ids = [paper_id của doc đúng]
   - `evaluate_pipeline()` chạy agent với mỗi câu → agent retrieve top-k docs → check: có doc_id nào trong ground_truth_doc_ids không? → `retrieval_hit = 1 or 0`
   - Tính `retrieval_hit_rate` = mean(retrieval_hit) = % câu hỏi agent retrieve đúng document
   - Compare 3 thế: baseline hit_rate cao → corrupted hit_rate thấp → repaired hit_rate gần baseline = chứng minh corruption impact + repair work

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - **Quality checks** (Người 3 làm): kiểm tra DataFrame schema, value validity, no null, dedup, summary not empty, etc. → phát hiện lỗi cấu trúc/format
   - **Freshness monitoring** (Người 3 làm): published_date of latest paper, % stale records (age > threshold) → phát hiện data cũ, không update
   - Cả hai đều output JSON nhưng phục vụ mục đích khác: quality = lỗi dữ liệu cấp hàng, freshness = lỗi thời gian

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   - Nếu dùng test set khác nhau: corrupted quality có thể tệ nhưng test set mới có thể dễ hơn → metrics không so sánh được
   - Cùng test set = cùng ground truth = cùng điều kiện → có thể cô lập được ảnh hưởng của corruption
   - Ví dụ: baseline hit_rate 0.8, corrupted hit_rate 0.5 (drop 30%) trực tiếp do corruption, không phải do test set khác

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - Load raw snapshot từ Crossref → clean lại bằng cleaning.py (phần tôi) → rebuild index → evaluate với **cùng test set**
   - Repaired hit_rate ≥ baseline hit_rate (hoặc gần) = repair thành công
   - Artifact: `papers_clean_repaired.csv`, `repaired_metrics.json`, comparison report so sánh 3 thế → chứng minh repair work

**Câu trả lời:**

Luồng end-to-end: raw Crossref → parse → **clean** (tôi) → embed → index → **evaluate với test set** (tôi) → metrics. Khi corrupt: cùng test set, metrics drop. Khi repair: chạy lại clean từ raw → cùng test set, metrics phục hồi. Chứng minh data quality ảnh hưởng trực tiếp đến agent quality.

## 8. Phân tích kết quả

### Metrics chính

Phần này sẽ được điền sau khi Người 5 chạy baseline/corrupted/repaired pipeline. Tôi (Người 2) đã chuẩn bị:
- Test set (12 samples, 4 loại) → deterministic evaluation
- Ground truth đối chiếu với agents answers (exact match field)
- Contract columns để downstream modules dùng

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      TBD |       TBD |      TBD | Metric này trực tiếp đo test set, nên phụ thuộc chất lượng cleaning (phần tôi) |
| `mean_token_f1`      |      TBD |       TBD |      TBD | Đo độ khớp answer text với ground truth, phụ thuộc ground truth được tạo đúng |
| `judge_accuracy`     |      TBD |       TBD |      TBD | LLM judge, phụ thuộc question/ground_truth quality |
| `mean_judge_score`   |      TBD |       TBD |      TBD | Điểm từ judge (1-5) |
| Quality checks         |      TBD |       TBD |      TBD | Được xác định bởi Người 3 |
| Freshness status       |      TBD |       TBD |      TBD | Được xác định bởi Người 3 |

### Kết luận từ số liệu

**Hai chuỗi nguyên nhân–bằng chứng mong đợi:**

1. **Data corruption** (Người 4 tạo: blank summary, old dates, missing docs) → **quality/freshness signal thay đổi** (summary_chars giảm, age_days tăng, stale % cao) → **agent metric thay đổi** (retrieval_hit_rate giảm, mean_token_f1 giảm vì agent trích từ summary rỗng).

2. **Repair action** (chạy clean lại từ raw) → **quality/freshness signal phục hồi** (summary_chars quay lại, age_days đúng, no stale) → **agent metric phục hồi** (retrieval_hit_rate ≈ baseline).

**Corruption dự kiến ảnh hưởng rõ nhất: Blank summary**
- Lý do: 3 papers trong test set đều hỏi về summary (1 sample per paper) → khi summary trở thành "", text_for_embedding mất 50% content → embedding chất lượng kém → retrieval miss
- Metric bị ảnh hưởng: retrieval_hit_rate, mean_token_f1

**Kết quả nào khác với kỳ vọng ban đầu (sẽ cập nhật sau baseline chạy)**
- Hiện tại chưa có dữ liệu baseline từ Người 5 → không thể so sánh được
- Sẽ cập nhật khi có artifacts: baseline_metrics.json, corrupted_metrics.json, repaired_metrics.json

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline phải deterministic và có contract rõ ràng**: Output schema phải được nhóm thống nhất trước khi code. Khi cleaning output 12 cột đúng dtype, downstream không phải defensive check → code sạch, integration dễ. Thứ tự operation (sort/dedupe) quan trọng → phải test sớm.

2. **Evaluation set là chiếc kính để đo data quality**: Không thể chỉ nhìn metrics cuối cùng mà không biết test set như thế nào. Ground truth phải lấy từ exact field mà agent trả lời → không thể hardcode hoặc random pick → phải systematic. Cùng test set cho baseline/corrupted/repaired là tiền đề để cô lập được data corruption impact.

3. **Ảnh hưởng dữ liệu thấm sâu**: Một cột (summary, date, title) bị corrupt → không chỉ ảnh hưởng retrieval (embedding quality) mà còn answer quality (qa.py extract từ metadata). Phải think end-to-end: raw data → cleaning → embedding + metadata → retrieval + answer → metrics.

### Nếu có thêm thời gian

**Cải thiện cụ thể: Great Expectations validation rules cho cleaning**
- Hiện tại: hand-written pandas checks, tổ chức bằng fixture
- Cải thiện: Dùng Great Expectations để define data quality "contract" (schema, expectation suite) → sinh tự động test từ spec
- Lý do: Scalability (khi corpus lớn từ hàng chục lên hàng triệu records, edge case tăng); reusability (hội team có thể share expectation suite); audit trail (Great Expectations output JSON report chi tiết)
- Cách đo: Chạy lại corruption scenario trên real data (khi Người 5 fetch từ Crossref) → validate test set sensitivity (corruption nào Great Expectations catch, corruption nào slip through → cải thiện expectation)
- Ước lượng: +4-6 giờ nếu tìm hiểu Great Expectations API

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
  - Tôi (Người 2) trực tiếp implement cleaning.py, testset.py, fixtures, 28 test cases
  - Hiểu được vấn đề (raw data messy, need deterministic cleaning + evaluation set), cách giải quyết (normalize, dedupe, sort, contract columns), và trade-off (dedupe theo title để exact lookup work)
  
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
  - Phần 7 trả lời chi tiết: raw Crossref → parse → **clean** (tôi) → embed → index → **test set** (tôi) → evaluate → metrics; corruption → repair cycle dùng cùng test set để đo impact
  
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
  - Code: branch feat/cleaning-testset, commits 8a69610 + 3f9dd8c + merge 1b63e7f
  - Tests: 28 pass (16 cleaning + 12 testset), pytest output có timestamp
  - Fixture: 7 PaperRecord (5 valid, 1 dup title, 1 empty title, 1 empty summary)
  
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
  - Phần 8 (metrics): đánh dấu TBD vì chờ Người 5 chạy pipeline với real data
  - Chỉ ghi kết quả của phần tôi: tests pass, cleaning logic đúng, test set schema đúng
  
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
  - Kiểm tra toàn báo cáo: không có URL API, không có credentials, chỉ có public GitHub repo link
  
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.
  - Viết từ đầu, mô tả chi tiết phần việc cụ thể của Người 2 (cleaning + testset), quyết định kỹ thuật (dedupe title), blocker (sort/dedupe order)

**Họ và tên:** Nguyễn Quang Vinh
**Ngày xác nhận:** 2026-08-06
