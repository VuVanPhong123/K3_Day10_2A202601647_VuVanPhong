# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phạm Sỹ Đức |
| MSSV | 2A202601601 |
| Khóa/Lớp | K3 |
| Tên nhóm | C502 |
| Vai trò chính | `data_corruption` |
| Repository | `K3_Day10_Data-Pipeline-Data-Observability` |
| Ngày hoàn thành | 06/08/2026 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Corruption scenarios | `src/ingestion/corruption.py`, `corrupt_clean_dataframe` | Clean DataFrame theo contract 12 cột, `target_doc_ids`, seed | Corrupted DataFrame và derived columns được rebuild | Hoàn thành |
| Scenario unit tests | `tests/test_corruption.py` | DataFrame synthetic tối thiểu 10 dòng | Test cho 6 helper, determinism, target priority, log và non-mutation | Hoàn thành |
| Corruption logging | `_write_log`, `data/results/corruption_log.json` | Trạng thái DataFrame trước/sau từng scenario | JSON log gồm row count, IDs, fields, before/after | Hoàn thành |
| Kiểm chứng tích hợp | `data/clean/`, `data/results/`, `data/quality/`, `data/reports/` | Baseline clean dataset và evaluation set dùng chung | Corrupted/repaired artifacts và comparison evidence | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra contract khi nối corruption flow | `src/pipelines/corruption_flow.py` và observability modules | Corrupted dataset được rebuild index, đánh giá trên cùng test set và tạo comparison report |
| Đối chiếu quality/freshness sau corruption | `src/observability/quality.py` | Xác nhận corrupted fail 3/11 quality checks và freshness chuyển sang stale |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Drop document quan trọng | `_drop_important_docs` | 1 dòng bị drop từ 24 xuống 23; ưu tiên document trong evaluation set | `corruption_log.json`, record `drop_important_docs` |
| Blank và inject noise vào summary | `_blank_summary`, `_inject_noise_summary` | Mỗi scenario tác động 4 document; noise không trùng các dòng đã blank | Log before/after và quality `summary_sufficient_length` |
| Truncate title | `_truncate_title` | 4 title bị cắt còn 10 ký tự, không tạo title rỗng | Log record `truncate_title` |
| Làm stale publication date | `_stale_publication_date` | 5 document bị lùi `published` và `updated` 3–5 năm | Freshness report: 8/26 stale rows, ratio 0.3077 |
| Thêm duplicate rows | `_add_duplicate_rows` | Thêm 3 dòng, đổi ID với hậu tố `-dup`; fingerprint duplicate check phát hiện 3 dòng | Quality corrupted: `no_duplicate_rows` fail, observed `3` |
| Rebuild derived columns | `_rebuild_derived_columns` | Cập nhật `summary_chars`, `age_days`, `text_for_embedding` sau corruption | Quality `age_days_valid` và `text_for_embedding_not_empty` pass |
| Đánh giá impact và repair | `corruption_flow.py`, metrics/quality artifacts | Retrieval hit rate giảm 1.0 → 0.25; repair khôi phục về 1.0 | `corruption_report.md` và các metrics JSON |

Output tổng hợp quan trọng nhất là `data/results/corruption_log.json`: log có 7 records gồm 6 scenario và 1 summary, tổng cộng 13 affected IDs, row count toàn flow từ 24 xuống sau drop rồi tăng lên 26 sau duplicate.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Baseline có clean dataset hợp lệ nên chưa chứng minh được hệ thống RAG phản ứng thế nào với dữ liệu xấu. Phần `data_corruption` tạo ra các lỗi có kiểm soát, ưu tiên document nằm trong ground-truth evaluation set, để quality/freshness checks và retrieval metrics có thể quan sát được impact. Sau đó pipeline integration dùng raw snapshot để repair và đánh giá lại trên cùng evaluation set.

### Cách triển khai

`corrupt_clean_dataframe` làm việc trên `df.copy(deep=True)` và dùng một `random.Random(seed)` cục bộ. Sáu scenario được chạy theo thứ tự cố định:

1. Drop document quan trọng với default ratio `0.20`.
2. Blank summary với default ratio `0.15`.
3. Append token noise vào summary khác với các dòng đã blank, ratio `0.15`.
4. Truncate title về tối đa 10 ký tự, ratio `0.15`.
5. Lùi `published` và `updated` 3–5 năm, ratio `0.20`.
6. Nhân bản tối thiểu 2 dòng hoặc 10% số dòng hiện tại, giá trị lớn hơn; ID bản sao có hậu tố `-dup`.

Ở mọi scenario, các dòng có `paper_id` trong `target_doc_ids` được chọn trước; chỉ khi không đủ mới fallback sang các dòng khác. Sau toàn bộ transform, các cột dẫn xuất được tính lại. Log lưu row count trước/sau, ID bị ảnh hưởng, field thay đổi và snapshot before/after bằng JSON UTF-8.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `pd.DataFrame` gồm `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `updated`, `age_days`, `summary_chars`, `text_for_embedding`, `abs_url`, `pdf_url` |
| Tham số | `output_log_path`, `target_doc_ids`, `seed` và các ratio/ngưỡng keyword-only |
| Output | DataFrame mới, giữ contract cột; các derived fields được rebuild |
| Log | `data/results/corruption_log.json` |
| Module sử dụng output | `src/pipelines/corruption_flow.py`, retrieval index, quality/freshness và reporting |
| Điều kiện lỗi xử lý | Thiếu cột contract, ratio ngoài `[0, 1]`, title length không hợp lệ, stale year bounds sai, duplicate minimum không hợp lệ |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** tạo baseline, corrupted và repaired artifacts; corrupted quality hoặc retrieval metrics giảm; repaired tiến gần baseline.
- **Kết quả thực tế:** flow end-to-end hoàn thành; corrupted quality `FAIL`, retrieval hit rate giảm còn `0.25`; repaired quality `PASS` và retrieval hit rate trở lại `1.0`.
- **Artifact/log:** `data/results/corruption_log.json`, `data/results/*_metrics.json`, `data/quality/{baseline,corrupted,repaired}.json`, `data/quality/freshness_*.json`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Nếu chọn document hoàn toàn ngẫu nhiên, corruption có thể không tác động đến ground-truth documents và evaluation metrics sẽ không chứng minh được impact.
- **Phương án 1:** Chọn ngẫu nhiên trên toàn bộ clean dataset.
- **Phương án 2:** Chọn trong `target_doc_ids` trước, sau đó fallback sang các dòng khác nếu thiếu số lượng cần thiết.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Cách này giữ randomness và reproducibility bằng seed nhưng tăng khả năng corruption tác động trực tiếp đến evaluation set. Trong run thực tế, các target IDs như `10.2118/234689-pa` và `10.1007/s10278-026-02086-9` xuất hiện ở các scenario chính.
- **Bằng chứng:** `retrieval_hit_rate` giảm từ `1.0000` xuống `0.2500`, `mean_token_f1` giảm từ `0.7500` xuống `0.0325`, và `judge_accuracy` giảm từ `0.7500` xuống `0.0000`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Nếu corruption chỉ rơi vào document ngoài evaluation set, retrieval metrics có thể vẫn giữ nguyên và không chứng minh được data impact.
- **Nguyên nhân gốc:** Logic chọn dòng không biết ground-truth document IDs hoặc không ưu tiên chúng.
- **Cách xử lý:** Bổ sung `target_doc_ids` vào API, chọn target trước ở mọi scenario, dùng seed cục bộ và ghi affected IDs vào log.
- **Cách xác minh sau khi sửa:** Log cho thấy các target IDs nằm ở đầu `affected_paper_ids`; metrics corrupted giảm rõ ràng và repaired trở lại baseline.
- **Điều học được:** Corruption cần được thiết kế theo evaluation contract; random corruption đơn thuần chưa đủ để chứng minh tác động đến agent.

Một giới hạn được ghi nhận trong run là Ragas không trả đủ các metric yêu cầu: baseline báo `answer_relevancy = 0.1808786` nhưng status `failed`, còn corrupted cũng báo invalid Ragas metrics. Đây là nhánh optional; các core metrics, quality checks và freshness vẫn được đánh giá độc lập và có kết quả hợp lệ.

## 7. Hiểu biết về luồng end-to-end

1. Crossref response được lưu thành raw snapshot, parse thành raw records, clean thành DataFrame 24 dòng, build `text_for_embedding`, tạo MiniLM embeddings và lưu vào Chroma index. Từ clean dataset, pipeline tạo evaluation set rồi đo baseline.
2. Evaluation set hiện có 12 câu hỏi và 3 unique ground-truth document IDs. Mỗi trạng thái baseline, corrupted và repaired đều dùng lại chính test set này; ground-truth IDs được truyền vào corruption để ưu tiên target documents.
3. Quality checks kiểm tra tính hợp lệ/completeness của dataset như summary length, duplicate fingerprint, ID và age. Freshness monitoring tập trung vào tuổi publication, số dòng stale và freshness threshold 180 ngày.
4. Dùng cùng test set giúp delta giữa ba trạng thái phản ánh thay đổi của dữ liệu/index thay vì thay đổi do bộ câu hỏi khác nhau.
5. Repair thành công khi dữ liệu được đọc lại từ raw snapshot, clean lại, tạo repaired index, quality/freshness trở về trạng thái pass và retrieval/answer metrics tiến gần baseline. Run này đạt cả ba điều kiện: repaired có 24 dòng, quality `11/11`, freshness `0` stale rows và core metrics khớp baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.2500 | 1.0000 | Giảm 75 điểm phần trăm sau corruption và phục hồi hoàn toàn |
| `mean_token_f1` | 0.7500 | 0.0325 | 0.7500 | Giảm 0.7175, cho thấy answer content bị ảnh hưởng mạnh |
| `judge_accuracy` | 0.7500 | 0.0000 | 0.7500 | LLM judge không còn đánh giá đáp án corrupted là đúng |
| `mean_judge_score` | 4 | 1 | 4 | Giảm 3 điểm rồi phục hồi |
| Quality checks | PASS 11/11 | FAIL 8/11 | PASS 11/11 | Corrupted fail summary length, duplicate fingerprint và stale ratio |
| Freshness status | PASS, stale 0/24 | FAIL, stale 8/26 | PASS, stale 0/24 | Stale ratio corrupted là 0.3077 |
| Ragas | Failed/invalid metrics | Failed/invalid metrics | Skipped | Không dùng làm core conclusion |

### Delta metrics dùng để đối chiếu

| Metric | Corrupted − Baseline | Repaired − Baseline | Kết luận |
| --- | ---: | ---: | --- |
| `retrieval_hit_rate` | -0.7500 | 0.0000 | Phục hồi hoàn toàn |
| `mean_token_f1` | -0.7175 | 0.0000 | Phục hồi hoàn toàn |
| `judge_accuracy` | -0.7500 | 0.0000 | Phục hồi hoàn toàn |
| `mean_judge_score` | -3.0000 | 0.0000 | Phục hồi hoàn toàn |
| Quality checks passed | -3 checks | 0 checks | PASS → FAIL → PASS |
| Freshness stale ratio | +0.3077 | 0.0000 | Fresh → stale → fresh |

### Kết luận từ số liệu

1. **Data corruption** làm mất/biến dạng document và metadata: summary check chỉ còn 19/26 dòng đạt ngưỡng, duplicate fingerprint quan sát được 3 dòng và stale ratio tăng lên 0.3077 → **quality/freshness chuyển từ PASS sang FAIL** → retrieval hit rate giảm `1.0000 → 0.2500`, mean token F1 giảm `0.7500 → 0.0325`.
2. **Repair từ raw snapshot và chạy lại cleaning** khôi phục clean dataset về 24 dòng → quality trở lại `11/11`, freshness trở lại `0` stale rows → retrieval hit rate, token F1, judge accuracy và mean judge score đều trở về baseline.

Corruption ảnh hưởng rõ nhất là tổ hợp `drop_important_docs` cùng blank/noise/truncate trên các target documents. Một run duy nhất không đủ để cô lập causal contribution của từng scenario, nhưng log và quality checks xác nhận stale date và duplicate fingerprint là hai tín hiệu dữ liệu rõ nhất; các thay đổi summary/title/date sau đó tác động trực tiếp tới nội dung retrieval context.

Kết quả khác kỳ vọng ban đầu là check `paper_id_unique` vẫn PASS với 26 dòng vì bản sao được đổi ID thành `-dup`. Tuy nhiên quality vẫn phát hiện duplicate qua fingerprint normalized title, summary, published và authors, với observed `3`. Điều này cho thấy kiểm tra duplicate cần nhìn cả nội dung record, không chỉ uniqueness của ID.

### Đối chiếu với Rubric mục 8

| Tiêu chí | Bằng chứng trong run | Kết quả |
| --- | --- | --- |
| Có mô phỏng corruption | 6 scenario trong `corruption.py`, log có 7 records gồm summary | Đạt |
| Đo được impact rõ | Retrieval hit rate giảm `1.0 → 0.25`; quality fail `3` checks; freshness stale ratio `0.3077` | Đạt |
| Có repaired state | `papers_clean_repaired.*`, repaired metrics, repaired quality/freshness | Đạt |
| Có comparison hợp lý | `data/reports/corruption_report.md` đối chiếu cùng 12 evaluation samples | Đạt |
| Repair tiến gần baseline | Repaired metrics và quality/freshness khớp baseline | Đạt |

Với các bằng chứng trên, phần Corruption & Comparison đáp ứng mức cao của Rubric mục 8. Điểm tổng của toàn bài vẫn phụ thuộc các mục ingestion, cleaning, retrieval, LLM, observability và pipeline integration do các thành viên khác phụ trách.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Corruption phải deterministic và có log chi tiết thì mới tái hiện được data issue và giải thích được metric delta.
2. Quality checks và freshness monitoring bổ sung cho nhau: summary/duplicate checks bắt lỗi nội dung và identity, còn freshness bắt lỗi publication date bị stale.
3. Trong RAG, thay đổi nhỏ ở các document nằm trong ground-truth set có thể làm retrieval hit rate và answer metrics giảm mạnh dù pipeline kỹ thuật vẫn chạy không lỗi.

### Nếu có thêm thời gian

Tôi sẽ chạy ablation riêng cho từng scenario và thêm bảng contribution theo từng corruption: chỉ drop, chỉ blank/noise, chỉ truncate, chỉ stale, chỉ duplicate. Mỗi ablation sẽ dùng cùng seed và evaluation set, sau đó so sánh quality delta, freshness delta và retrieval hit rate để tách rõ tác động của từng loại corruption.

### Ma trận artifact và validation

| Artifact | Vai trò bằng chứng | Trạng thái run |
| --- | --- | --- |
| `data/results/corruption_log.json` | Scenario, seed, row count, affected IDs và before/after | Có |
| `data/clean/papers_clean_corrupted.*` | Dataset sau corruption | Có |
| `data/clean/papers_clean_repaired.*` | Dataset sau repair từ raw snapshot | Có |
| `data/results/baseline_metrics.json` | Baseline retrieval/answer metrics | Có |
| `data/results/corrupted_metrics.json` | Impact của corruption | Có |
| `data/results/repaired_metrics.json` | Mức phục hồi sau repair | Có |
| `data/quality/{baseline,corrupted,repaired}.json` | Quality checks theo ba trạng thái | Có |
| `data/quality/freshness_*.json` | Freshness theo ba trạng thái | Có |
| `data/reports/corruption_report.md` | Comparison report được sinh từ payload thật | Có |

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Sỹ Đức

**Ngày xác nhận:** 06/08/2026
