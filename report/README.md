# Hướng dẫn làm bài và nộp báo cáo

Thư mục `report/` cung cấp mẫu báo cáo cho bài tập này. Bài lab hỗ trợ cả làm nhóm (3–5 thành viên) và **làm cá nhân** — trường hợp làm cá nhân, một người phụ trách toàn bộ các khối công việc và vẫn phải hiểu luồng end-to-end.

## 1. Quy định về báo cáo

Nếu làm cá nhân, chỉ cần nộp một bản báo cáo dựa trên mẫu [`individual_report.md`](individual_report.md), mô tả vai trò (toàn bộ pipeline), phần việc, kết quả và mức hiểu của bạn. Đặt tên file theo quy ước:

```text
<MSSV>_HoTen.md
```

Không cần `group_report.md` khi làm cá nhân — mọi nội dung so sánh baseline/corrupted/repaired đưa thẳng vào báo cáo cá nhân.

Nếu làm nhóm, mỗi nhóm nộp thêm một `group_report.md` đại diện cho kết quả chung, bên cạnh báo cáo cá nhân của từng thành viên.

## 2. Kết quả chung cần đạt

Mọi bài làm cần chứng minh được toàn bộ quan hệ:

```text
Nguồn Crossref
    -> raw records
    -> cleaned dataset
    -> embedding/index
    -> evaluation baseline
    -> quality và freshness signals
    -> corrupted dataset
    -> evaluation sau corruption
    -> repair
    -> so sánh baseline/corrupted/repaired
```

Không chỉ báo cáo rằng lệnh đã chạy thành công. Kết luận cần dựa trên artifact và số liệu thực tế, đặc biệt:

- `retrieval_hit_rate`
- `mean_token_f1`
- `judge_accuracy`
- `mean_judge_score`
- kết quả data quality checks
- trạng thái freshness

Các trạng thái baseline, corrupted và repaired phải được đánh giá trên cùng evaluation set để phép so sánh có ý nghĩa.

## 3. Nguyên tắc chung khi thực hiện

### Giữ một môi trường thống nhất

Khi làm nhóm, tất cả thành viên cần thống nhất (khi làm cá nhân, tự giữ nhất quán xuyên suốt các giai đoạn):

- cấu trúc thư mục và đường dẫn artifact có sẵn trong project;
- không thay đổi chữ ký hàm mà các module khác đang gọi.

### Chia theo deliverable, không chia máy móc theo package

Mỗi phần việc phải có:

- owner chính;
- input cần nhận;
- output phải bàn giao;
- cách xác minh.

Không nên chia theo kiểu mỗi người viết một file độc lập rồi ghép lại vào cuối. Các phần ingestion, cleaning, evaluation, observability và pipeline phụ thuộc trực tiếp vào schema và artifact của nhau.

### Phải hiểu luồng end-to-end

Owner chịu trách nhiệm chính cho module được giao, nhưng không đồng nghĩa chỉ owner mới cần hiểu module đó (khi làm cá nhân, bạn là owner của mọi module nên đây là yêu cầu bắt buộc). Bạn phải giải thích được:

- dữ liệu đi qua pipeline như thế nào;
- module của mình nhận input gì và tạo output gì;
- corruption tác động đến dữ liệu và agent ra sao;
- artifact hoặc metric nào chứng minh kết luận;
- pipeline được repair và xác minh lại như thế nào.

## 4. Phần việc và báo cáo vai trò

Các khối công việc dưới đây cần có một owner chính mỗi khối. Khi làm cá nhân, bạn là owner của toàn bộ các khối; khi làm nhóm, phân công theo owner chính cho từng khối và nêu rõ phạm vi trong `individual_report.md`.

| Khối                      | File trọng tâm                                                      | Output cần kiểm tra                                            |
| -------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Raw ingestion              | `src/ingestion/crossref.py`                                         | Raw response và raw records trong`data/raw/`                  |
| Cleaning và data modeling | `src/ingestion/cleaning.py`                                         | Cleaned CSV/JSON, schema và`text_for_embedding`               |
| Evaluation set             | `src/evaluation/testset.py`                                         | Test set trong`data/eval/`                                     |
| Quality và freshness      | `src/observability/quality.py`                                      | Quality/freshness artifacts trong`data/quality/`               |
| Reporting                  | `src/observability/reporting.py`                                    | Báo cáo trong`data/reports/`                                 |
| Baseline orchestration     | `src/pipelines/phase1.py`                                           | Baseline metrics và đầy đủ artifact của pha 1              |
| Corruption và repair      | `src/ingestion/corruption.py`, `src/pipelines/corruption_flow.py` | Corruption log, corrupted/repaired metrics và comparison report |

Trình tự phụ thuộc cần giữ:

1. Hoàn thành ingestion và xác minh raw records.
2. Hoàn thành cleaning và kiểm tra schema trước khi build index.
3. Tạo evaluation set từ cleaned dataset.
4. Hoàn thành baseline pipeline trước khi chạy corruption flow.
5. Dùng lại cùng evaluation set cho baseline, corrupted và repaired.
6. Đọc artifacts và metrics trước khi viết kết luận.

Trong `individual_report.md`, cần phân biệt rõ:

- phần đã hoàn thành;
- phần mới dừng ở mức thử nghiệm;
- phần chưa chạy được và blocker còn lại;
- bằng chứng thực tế tương ứng với từng kết luận.

## 5. Hướng dẫn làm bài (cá nhân hoặc theo nhóm)

### Làm cá nhân (1 người)

| Vai trò   | Nhiệm vụ sở hữu                                                                     | Output bàn giao                                                              |
| --------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| Toàn bộ pipeline | `crossref.py`, `cleaning.py`, `testset.py`, `quality.py`, `reporting.py`, `corruption.py`, `phase1.py`, `corruption_flow.py` | Raw/clean data, evaluation set, quality/freshness artifacts, corruption log, baseline/corrupted/repaired metrics và comparison report |

Vì chỉ có một owner, hoàn thành tuần tự theo trình tự phụ thuộc ở mục 4 (ingestion → cleaning/test set → observability → baseline → corruption/repair) thay vì chia song song. Xem chi tiết từng giai đoạn trong [`../job.md`](../job.md).

### Nhóm 3 thành viên

| Thành viên   | Vai trò chính                  | Nhiệm vụ sở hữu                                                        | Output bàn giao                                                     |
| -------------- | -------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Thành viên 1 | Data ingestion & cleaning owner  | `crossref.py`, `cleaning.py`; thống nhất raw/clean schema            | Raw records, cleaned dataset và mô tả cleaning rules              |
| Thành viên 2 | Evaluation & observability owner | `testset.py`, `quality.py`, `reporting.py`                           | Evaluation set, quality/freshness results và report functions       |
| Thành viên 3 | Corruption & integration owner   | `corruption.py`, `phase1.py`, `corruption_flow.py`; chạy tích hợp | Baseline/corrupted/repaired artifacts, metrics và comparison report |

Với nhóm 3, khối tích hợp tương đối lớn. Thành viên 1 hỗ trợ kiểm tra dữ liệu repair; thành viên 2 hỗ trợ xác minh metrics và báo cáo cho thành viên 3.

### Nhóm 4 thành viên — khuyến nghị

| Thành viên   | Vai trò chính                   | Nhiệm vụ sở hữu                                      | Output bàn giao                                          |
| -------------- | --------------------------------- | -------------------------------------------------------- | --------------------------------------------------------- |
| Thành viên 1 | Source owner                      | `crossref.py`; fetch, retry, parse và lưu raw data   | Raw response, raw records và schema đầu vào           |
| Thành viên 2 | Data model & evaluation-set owner | `cleaning.py`, `testset.py`                          | Cleaned dataset,`text_for_embedding` và evaluation set |
| Thành viên 3 | Observability owner               | `quality.py`, `reporting.py`                         | Quality checks, freshness và báo cáo Markdown          |
| Thành viên 4 | Corruption & integration owner    | `corruption.py`, `phase1.py`, `corruption_flow.py` | Hai flow chạy end-to-end và bộ metrics so sánh        |

Đây là cấu hình cân bằng nhất cho workload hiện tại. Thành viên 4 chịu trách nhiệm điều phối tích hợp, không phải tự sửa toàn bộ lỗi của các module khác.

### Nhóm 5 thành viên

| Thành viên   | Vai trò chính                       | Nhiệm vụ sở hữu                                              | Output bàn giao                                                    |
| -------------- | ------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| Thành viên 1 | Source owner                          | `crossref.py`                                                  | Raw response, raw records và schema                                |
| Thành viên 2 | Cleaning & test-set owner             | `cleaning.py`, `testset.py`                                  | Cleaned dataset và evaluation set                                  |
| Thành viên 3 | Observability owner                   | `quality.py`, `reporting.py`                                 | Quality/freshness artifacts và report functions                    |
| Thành viên 4 | Corruption & repair owner             | `corruption.py`; kiểm tra dữ liệu corrupted/repaired        | Corruption log, corruption scenarios và dữ liệu repair hợp lệ  |
| Thành viên 5 | Pipeline integration & evidence owner | `phase1.py`, `corruption_flow.py`; tái hiện toàn bộ flow | Lệnh chạy, metrics, comparison report và bằng chứng tích hợp |

Thành viên 5 không chỉ làm tài liệu. Vai trò này chịu trách nhiệm kỹ thuật cho orchestration, reproducibility và kiểm tra sự nhất quán giữa report với artifact.

## 6. Phối hợp và tích hợp

Trước khi code (khi làm nhóm: trước khi làm song song; khi làm cá nhân: trước khi bắt đầu giai đoạn 1), chốt contract dùng chung:

| Contract          | Nội dung cần thống nhất                                                   |
| ----------------- | ----------------------------------------------------------------------------- |
| Raw schema        | Các trường của một paper record và cách xử lý trường thiếu        |
| Clean schema      | Tên cột, kiểu dữ liệu, quy tắc loại bỏ/deduplicate                    |
| Document identity | Cách tạo và giữ ổn định`paper_id`/document ID                        |
| Evaluation set    | Schema câu hỏi, ground truth và document IDs                               |
| Artifact paths    | Sử dụng đúng đường dẫn được cấu hình trong`src/core/config.py` |
| Metrics           | Dùng cùng tên metric và cùng evaluation set                              |
| Repair            | Repair lại từ nguồn raw/baseline nào và cách xác minh                  |

Trước khi tích hợp phần việc, kiểm tra:

- input/output có đúng contract chung không;
- có hard-code path, model hoặc secret không;
- thay đổi có làm hỏng module kế tiếp không;
- có artifact hoặc lệnh xác minh đi kèm không.

## 7. Cách xác minh bài làm

### Chạy baseline

Với `uv`:

```bash
uv run python script/run_phase1.py
```

Với môi trường `pip` đã được kích hoạt:

```bash
python script/run_phase1.py
```

### Chạy corruption flow

Với `uv`:

```bash
uv run python script/run_corruption_flow.py
```

Với môi trường `pip` đã được kích hoạt:

```bash
python script/run_corruption_flow.py
```

Repo hiện không cung cấp test hoặc grader tự động làm tiêu chí pass cuối cùng. Việc xác minh dựa trên lệnh pipeline, artifacts thực tế, metrics, báo cáo và [`Rubric.md`](../Rubric.md).

Tối thiểu cần kiểm tra:

- `data/raw/`
- `data/clean/`
- `data/embeddings/`
- `data/eval/`
- `data/results/baseline_metrics.json`
- `data/quality/`
- `data/reports/phase1_report.md`
- `data/results/corruption_log.json`
- `data/reports/corruption_report.md`

Không đánh dấu hoàn thành nếu report mô tả kết quả không khớp với artifact thực tế.

## 8. Definition of Done

- [ ] Có mô tả rõ vai trò, phạm vi và output (của bạn nếu làm cá nhân; của từng thành viên nếu làm nhóm).
- [ ] Mỗi deliverable có owner và output rõ ràng.
- [ ] Có thể chạy lại toàn bộ pipeline từ hướng dẫn trong README/Guide.
- [ ] Báo cáo cá nhân (`<MSSV>_HoTen.md`) khớp với code, artifacts và metrics. Nếu làm nhóm, `group_report.md` cũng phải khớp.
- [ ] Có thể giải thích luồng end-to-end, không chỉ phần mình trực tiếp code.
- [ ] Không có `.env`, API key hoặc secret trong repository, report hoặc log.

## 9. Nguyên tắc báo cáo trung thực

- Không ghi “đã chạy thành công” nếu chưa có output mới để kiểm chứng.
- Không sao chép cùng một nội dung báo cáo thành viên cho mọi người.
- Không nhận ownership cho file hoặc hàm mà mình không trực tiếp thực hiện.
- Nếu một phần chưa hoàn thành, ghi rõ trạng thái, lỗi nguyên văn đã che secret, nguyên nhân đã xác định và bước tiếp theo.
- Số liệu của các nhóm có thể khác nhau vì Crossref là nguồn sống. Chỉ so sánh các trạng thái trong cùng bài làm, trên cùng test set và cấu hình.
