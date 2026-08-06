
# Cấu hình model đề xuất

## Mặc định: Gemini

```dotenv
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
GOOGLE_API_KEY=your_key_here

RUN_RAGAS=0
REFRESH_SOURCE=0
REFRESH_TEST_SET=0
```

`gemini-3.5-flash-lite` hiện là model stable/GA. `gemini-3.1-flash-lite` cũng là model stable và có thể dùng làm fallback; không dùng tên có hậu tố `-preview` vì bản preview 3.1 đã bị ngừng hoạt động. ([Google AI for Developers][1])

Gemini fallback:

```dotenv
LLM_MODEL=gemini-3.1-flash-lite
```

## Phương án OpenAI

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.4-nano
OPENAI_API_KEY=your_key_here

RUN_RAGAS=0
```

`gpt-5.4-nano` phù hợp cho tác vụ judge có cấu trúc, hỗ trợ Chat Completions và Structured Outputs. ([OpenAI Developers][2])

Repo hiện mặc định `gemini-2.5-flash`, nên người tích hợp cần cập nhật `.env.example` và giá trị mặc định trong `config.py`.

Vì làm một mình, chạy fixture/mock trước để phát triển nhanh, rồi mới chạy evaluation bằng API key thật. Chỉ bật `RUN_RAGAS=1` một lần ở vòng kiểm tra cuối vì Ragas tạo thêm nhiều API calls; code hiện cũng mặc định bỏ qua Ragas nếu biến này chưa bật.

---

# Trình tự công việc khi làm một mình

Làm cá nhân nên không cần chia branch theo người; thực hiện tuần tự theo dependency thật của pipeline (ingestion → cleaning/test set → observability → corruption → tích hợp). Có thể vẫn dùng branch theo giai đoạn (ví dụ `feat/crossref-ingestion`, `feat/cleaning-testset`, ...) để commit gọn, nhưng chỉ một người merge nên không cần đợi review chéo.

## Giai đoạn 1 — Crossref ingestion

**File cần hoàn thành**

```text
src/ingestion/crossref.py
tests/test_crossref.py
tests/fixtures/crossref_response.json
```

**Công việc**

* Implement `parse_crossref_payload()`.
* Parse DOI, title, abstract, authors, subject, published/updated, URL.
* Làm sạch XML/HTML trong abstract.
* Loại record thiếu DOI, title hoặc abstract.
* Implement gọi Crossref với timeout và retry/backoff cho `429`, `500`, `502`, `503`, `504`.
* Lưu nguyên response vào `crossref_response.json`.
* Lưu danh sách `PaperRecord` vào `crossref_records.json`.
* Implement `load_raw_records()`.

Các chức năng này hiện đều là TODO độc lập.

**Điều kiện hoàn thành**

* Test parse chạy hoàn toàn offline bằng fixture.
* Raw response và raw records đều được ghi UTF-8.
* Retry có số lần tối đa, không lặp vô hạn.
* Không cần bất kỳ LLM key nào.

---

## Giai đoạn 2 — Cleaning và evaluation test set

**File cần hoàn thành**

```text
src/ingestion/cleaning.py
src/evaluation/testset.py
tests/test_cleaning.py
tests/test_testset.py
```

**Công việc cleaning**

* Chuẩn hóa whitespace.
* Chuẩn hóa title, summary, authors và categories.
* Parse ngày `published`, `updated`.
* Tính `age_days`.
* Tạo:

  * `authors_joined`
  * `categories_joined`
  * `summary_chars`
  * `text_for_embedding`
* Loại row lỗi và duplicate.
* Sắp xếp kết quả deterministic.

**Công việc test set**

* Tạo 8–12 câu hỏi deterministic.
* Có đủ bốn loại:

  * summary
  * authors
  * publication date
  * categories
* Mỗi sample phải có:

  * `id`
  * `question_type`
  * `question`
  * `ground_truth`
  * `ground_truth_doc_ids`

Hai file này đang là TODO hoàn toàn.

**Điều kiện hoàn thành**

* Có thể phát triển ngay bằng danh sách `PaperRecord` giả, không cần đợi người 1.
* Chạy hai lần trên cùng input phải tạo cùng thứ tự row và cùng test set.
* Câu hỏi nên chứa exact title trong dấu `'...'` vì `qa.py` hỗ trợ exact lookup theo mẫu này.

---

## Giai đoạn 3 — Data observability và reports

**File cần hoàn thành**

```text
src/observability/quality.py
src/observability/reporting.py
tests/test_quality.py
tests/test_reporting.py
```

**Công việc quality**

Tạo từng check với cấu trúc thống nhất:

```python
{
    "name": "paper_id_unique",
    "success": True,
    "observed": 24,
    "expected": 24,
    "details": {}
}
```

Các check tối thiểu:

* Row count đủ.
* `paper_id` không null.
* `paper_id` unique.
* `title` không rỗng.
* `summary` không rỗng và đủ dài.
* `text_for_embedding` không rỗng.
* Không có duplicate.
* Tỷ lệ stale records.
* Latest publication date có nằm trong freshness threshold.

**Công việc reporting**

* Baseline Markdown report.
* Bảng metrics.
* Bảng quality checks.
* Freshness summary.
* Comparison report gồm baseline/corrupted/repaired.
* Hiển thị cả giá trị tuyệt đối và delta.

Các hàm quality, freshness và reporting hiện đều chưa implement.

**Điều kiện hoàn thành**

* Làm hoàn toàn bằng DataFrame synthetic, không phụ thuộc ingestion.
* Mỗi report phải được sinh từ payload thật, không hard-code số.
* Pandas checks là bắt buộc; Great Expectations chỉ làm sau nếu còn thời gian.

---

## Giai đoạn 4 — Data corruption

**File cần hoàn thành**

```text
src/ingestion/corruption.py
tests/test_corruption.py
```

**Công việc**

Implement các corruption scenario:

* Drop một số document quan trọng.
* Blank summary.
* Inject noise.
* Truncate title.
* Làm publication date cũ đi.
* Thêm duplicate.
* Rebuild:

  * `summary_chars`
  * `age_days`
  * `text_for_embedding`
* Ghi log ID nào bị tác động, trước và sau thay đổi.

File này hiện là một TODO độc lập.

**Nên mở rộng signature ngay từ đầu**

```python
def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path,
    target_doc_ids: set[str] | None = None,
) -> pd.DataFrame:
```

Ở giai đoạn tích hợp (giai đoạn 5), truyền `ground_truth_doc_ids` từ test set vào tham số này. Nếu corruption chỉ tác động ngẫu nhiên vào các document không xuất hiện trong evaluation set, metrics có thể không giảm và bài sẽ không chứng minh được impact.

**Điều kiện hoàn thành**

* Corruption deterministic, dùng seed hoặc quy tắc cố định.
* Không sửa DataFrame đầu vào tại chỗ.
* Log chứa scenario, số row, document ID và trường bị thay đổi.
* Test xác nhận ít nhất một quality check sẽ fail.

**Lưu ý:** repair không nằm trong file này. Repair phải đọc lại raw snapshot rồi chạy lại cleaning để chứng minh khả năng phục hồi dữ liệu.

---

## Giai đoạn 5 — Integration, provider và end-to-end

**File cần hoàn thành**

```text
src/core/config.py
src/retrieval/llm.py
src/pipelines/phase1.py
src/pipelines/corruption_flow.py
.env.example
README.md
tests/test_pipelines.py
tests/test_llm_config.py
```

**Công việc provider**

* Đặt default thành `gemini-3.5-flash-lite`.
* Chỉ kiểm thử hai provider:

  * Gemini
  * OpenAI
* Không yêu cầu Anthropic, OpenRouter, Ollama hoặc custom key.
* Không hard-code key.
* Có lỗi rõ ràng khi thiếu key.
* Với Gemini 3.x, nên bỏ hoặc không bắt buộc `temperature`; Google đã đánh dấu các sampling parameter như `temperature`, `top_p`, `top_k` là deprecated với dòng model mới.

Không bắt buộc xóa code hỗ trợ provider cũ; chỉ không sử dụng hoặc yêu cầu credential của chúng. Starter hiện đã có abstraction cho nhiều provider.

### Baseline pipeline

Implement `phase1.py`:

```text
settings
→ load raw hoặc fetch Crossref
→ cleaning
→ lưu clean CSV/JSON
→ build Chroma index
→ tạo/load test set
→ evaluate
→ quality
→ freshness
→ Markdown report
→ optional agent demo
```

`phase1.py` hiện chưa có implementation.

### Corruption pipeline

Implement `corruption_flow.py`:

```text
load baseline artifacts
→ corrupt clean dataset
→ rebuild corrupted index
→ evaluate bằng test set cũ
→ corrupted quality/freshness
→ load raw snapshot
→ clean lại thành repaired dataset
→ rebuild repaired index
→ evaluate bằng test set cũ
→ repaired quality/freshness
→ comparison report
```

`corruption_flow.py` cũng đang hoàn toàn là TODO.

### Sửa thêm trong config

Hiện config chỉ có một path `freshness_report`, trong khi cần lưu ba trạng thái. Nên thêm:

```python
baseline_freshness_report
corrupted_freshness_report
repaired_freshness_report
```

Hoặc tạo trực tiếp:

```text
data/quality/freshness_baseline.json
data/quality/freshness_corrupted.json
data/quality/freshness_repaired.json
```

**Điều kiện hoàn thành**

* Pipeline tests dùng monkeypatch, không gọi mạng hoặc API thật.
* Chỉ chạy end-to-end với key thật ở giai đoạn kiểm tra cuối, sau khi các giai đoạn trước đã ổn định.
* Không commit `.env`, API key, Chroma database hoặc artifact quá lớn.

---

# DataFrame contract phải chốt trước khi code

Tự chốt tối thiểu các cột sau trước khi code, để tránh phải sửa lại schema giữa chừng khi các giai đoạn sau phụ thuộc vào nó:

| Cột                  | Kiểu            | Bắt buộc |
| -------------------- | --------------- | -------: |
| `paper_id`           | `str`           |       Có |
| `title`              | `str`           |       Có |
| `summary`            | `str`           |       Có |
| `authors_joined`     | `str`           |       Có |
| `categories_joined`  | `str`           |       Có |
| `published`          | ISO date string |       Có |
| `updated`            | ISO date string |   Nên có |
| `age_days`           | `int`           |       Có |
| `summary_chars`      | `int`           |       Có |
| `text_for_embedding` | `str`           |       Có |
| `abs_url`            | `str`           |       Có |
| `pdf_url`            | `str`           |       Có |

`index.py` hiện truy cập trực tiếp nhiều cột trong bảng này; nếu đổi tên cột giữa các giai đoạn mà không cập nhật đồng bộ thì lỗi chỉ xuất hiện lúc integration.

---

# Cách làm tuần tự cho 1 người

Làm một mình thì không có song song thật sự — đi lần lượt theo dependency, mỗi giai đoạn dùng mock/fixture để không phải chờ giai đoạn trước hoàn thiện 100% mới bắt đầu viết code.

## Bước 1 — Viết trước bằng mock/fixture

```text
Giai đoạn 1 (Crossref): code với fixture crossref_response.json giả.
Giai đoạn 2 (Cleaning + test set): code với danh sách PaperRecord giả.
Giai đoạn 3 (Quality/report): code với DataFrame giả.
Giai đoạn 4 (Corruption): code với DataFrame giả.
Giai đoạn 5 (Pipeline skeleton + model config): code với mock tests.
```

Có thể phác thảo skeleton của cả 5 giai đoạn sớm nếu đã chốt DataFrame contract và function signatures, nhưng chỉ hoàn thiện và chạy thật theo đúng thứ tự bên dưới.

## Bước 2 — Hoàn thiện và merge tuần tự

Hoàn thiện và tự kiểm tra theo thứ tự:

```text
1. feat/crossref-ingestion
2. feat/cleaning-testset
3. feat/observability-reports
4. feat/data-corruption
5. feat/pipeline-integration
```

Giai đoạn 5 (tích hợp) hoàn thiện cuối vì nó gọi vào tất cả các giai đoạn trước, nhưng có thể viết skeleton và mock test từ đầu. Khi cần đổi contract giữa các giai đoạn, ghi lại thay đổi trong commit message trước khi sửa để tránh quên vì sao đã đổi.

## Bước 3 — Integration bằng key thật

```powershell
Copy-Item .env.example .env
uv sync
uv run pytest
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

Sau khi hai flow đã chạy ổn mới thử:

```dotenv
RUN_RAGAS=1
```

Chỉ cần bật Ragas cho baseline hoặc một vòng final nhỏ để tiết kiệm API call.

---

# Tiêu chí nghiệm thu cuối

Baseline phải có:

```text
data/raw/crossref_response.json
data/raw/crossref_records.json
data/clean/papers_clean.csv
data/clean/papers_clean.json
data/embeddings/papers_embeddings.json
data/eval/test_set.json
data/results/baseline_metrics.json
data/results/baseline_answers.json
data/quality/...
data/reports/phase1_report.md
```

Corruption flow phải có:

```text
papers_clean_corrupted.*
papers_embeddings_corrupted.json
corruption_log.json
corrupted_metrics.json
corrupted_answers.json

papers_clean_repaired.*
papers_embeddings_repaired.json
repaired_metrics.json
repaired_answers.json

corruption_report.md
```

Các artifact này đúng với đầu ra được mô tả trong README và Guide.

Bài chỉ được coi là thành công khi:

```text
corrupted quality < baseline quality
hoặc
corrupted retrieval/answer metrics < baseline metrics

và

repaired metrics tiến gần hoặc quay lại baseline
```

Không cần mọi metric đều giảm, nhưng phải có ít nhất một thay đổi rõ ràng, hợp lý và được giải thích trong comparison report.

[1]: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite?authuser=4 "https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite?authuser=4"
[2]: https://developers.openai.com/api/docs/models/gpt-5.4-nano "https://developers.openai.com/api/docs/models/gpt-5.4-nano"
