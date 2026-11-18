# Báo cáo Day 09 — Nguyễn Thành Tài, MSHV 202603038

## 1. Kết luận

Pipeline quét 224 ảnh raw, nhận 202 ảnh và loại 22 ảnh ở bước intake. Sau mô phỏng review 80 ảnh, manifest của `clean_v1` có 202 ảnh; pipeline kết luận **Hold** vì còn cảnh báo chưa duyệt trên 29/202 ảnh (14,36%), cao hơn ngưỡng 10%. Không còn lỗi bắt buộc; export hiện tại là bản nháp để thử nghiệm, chưa được phát hành.

## 2. Lỗi và phân việc

Số liệu lấy từ `02_error_list_v1.csv`: 22 issue intake trên 224 ảnh raw và 168 issue QC trên 202 ảnh được nhận. Cột “vấn đề/đối tượng” là số issue / số ảnh duy nhất, riêng hai dòng cấp dataset ghi rõ đơn vị. Máy chỉ tự sửa cú pháp hoặc loại ảnh theo quy tắc; cảnh báo ý nghĩa do người xem.

| Mã lỗi | Vấn đề/đối tượng | Ai xử lý | Lý do |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2/2 | Máy | Không đọc được ảnh, loại ở intake. |
| `BAD_SIZE` | 3/3 | Máy | Cạnh ngắn dưới 250 px, loại khỏi dataset. |
| `DUP_IMAGE_NEAR` | 4/4 | Máy | Loại ảnh gần trùng theo ngưỡng pHash đã calibrate. |
| `LEAK_TEST` | 5/5 | Máy | Loại ảnh trùng kho test/validation để tránh rò rỉ. |
| `DUP_IMAGE_EXACT` | 8/8 | Máy | Loại ảnh trùng chính xác. |
| `MISSING_LABEL_FILE` | 6/6 | Người | Máy không thể tự đoán nhãn; chuyển người gán. |
| `EMPTY_LABEL` | 12/12 | Người | Cần xác định ảnh nền thật hay đang thiếu nhãn. |
| `DUP_BOX` | 7/7 | Máy | Bỏ dòng box trùng cùng lớp ở phía sau. |
| `BAD_FORMAT` | 3/3 | Máy | Bỏ dòng không đúng định dạng YOLO. |
| `BOX_HUGE` | 3/3 | Người | Box phủ diện tích lớn cần đối chiếu ảnh. |
| `BAD_CLASS_ID` | 6/6 | Máy | Bỏ dòng có ID lớp ngoài danh sách. |
| `BOX_TINY` | 6/4 | Người | Box nhỏ có thể là vật nhỏ thật hoặc nhãn sai. |
| `BOX_OUT_OF_IMAGE` | 8/8 | Máy | Cắt phần vượt biên; ghi từng thay đổi vào `03_fixes.csv`. |
| `BOX_ZERO` | 4/4 | Máy | Bỏ box có chiều rộng hoặc chiều cao bằng 0. |
| `BAD_CLASS_NAME` | 2 issue / 1 YAML | Máy | Chuẩn hóa tên lớp trong `data.yaml`. |
| `CLASS_RARE` | 4 issue / toàn dataset | Người | Token hiếm `-1,4,7,93` là ID sai, không phải lớp hợp lệ thiếu dữ liệu; biến mất sau khi máy bỏ dòng `BAD_CLASS_ID`. |
| `POSSIBLE_MISSING` | 44/43 | Người | Model thấy vật nhưng không khớp box nhãn. |
| `POSSIBLE_LOOSE_BOX` | 22/21 | Người | Model và nhãn có thể cùng vật nhưng box lệch/lỏng. |
| `POSSIBLE_WRONG_CLASS` | 16/16 | Người | Đối chiếu lớp dự đoán với ảnh. |
| `POSSIBLE_FALSE_POS` | 25/24 | Người | Box nhãn không khớp dự đoán; model cũng có thể sai. |

`05_review_queue.csv` có 118 ảnh; bộ mô phỏng đã xem 80 ảnh theo ngân sách. Trong 80 ảnh đó có 86 cảnh báo ngữ nghĩa (`POSSIBLE_*`) trên 73 ảnh, chưa đồng nghĩa với 86 lỗi đã xác nhận. `img_0020` đứng đầu, priority 11.524, do cộng `FIXED_DROP_LINE`, `POSSIBLE_MISSING`, `POSSIBLE_WRONG_CLASS` theo trọng số và confidence. `03_fixes.csv` có 20 lần bỏ dòng, 8 lần clip, 1 lần đổi tên lớp và 6 lần chuyển người gán; 6 lần chuyển người không tạo nhãn rỗng.

## 3. Calibration hai ngưỡng

Các chỉ số dưới đây là precision/recall trên tập calibration có lỗi chèn sẵn, lấy từ `calibration_report.md`.

| Tham số | Mặc định → chọn | Precision / Recall trước → sau | Lý do |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → 10 | `DUP_IMAGE_NEAR`: 1.00/0.50 → 1.00/0.67; exact: giữ 1.00/1.00 | Ngưỡng 10 giữ cả các cặp raw khoảng cách 6 và 10, nhưng tránh ca loại nhầm ở 16. Chấp nhận bỏ sót thêm 1/6 ca calib so với 16 để giảm rủi ro tự động xóa ảnh tốt. |
| `second_opinion.conf` | 0.25 → 0.7 | Wrong class: 0.56/0.83 → 0.62/0.83; missing: 0.50/1.00 → 0.58/0.88; loose box: 0.29/0.40 → 0.50/0.20; false positive: giữ 0.36/1.00 | Tăng precision nhưng đánh đổi recall. So với `conf=0.8` (missing recall 0.75), mức 0.7 giữ recall 0.875. False positive dùng `fp_conf` riêng. |

Calibration có thể đánh lừa: ở ngưỡng 16, near-duplicate có precision 1.00 trên 6 ca chèn, nhưng `img_0011`/`img_0008` của raw bị báo trùng dù tôi đã xem và xác nhận là hai cảnh khác nhau. Hai cặp `img_0076`/`img_0042` và `img_0143`/`img_0037` là cùng cảnh có biến đổi, đều pHash 0, vẫn được bắt ở ngưỡng 10. Vì vậy chọn lại 10, không chọn chỉ theo F1 calib. Tại 10, bắt 4/6 ca near-duplicate, bỏ sót 2/6. Bộ calib 39 ảnh không có ca `LEAK_TEST`, nên không suy diễn recall phát hiện rò rỉ từ bảng này. Chọn ngưỡng dùng calib và raw, không xem ảnh/nhãn test để điều chỉnh.

## 4. Cửa chặn và điểm mù

Chạy `python -X utf8 -m pipeline.run --budget 0 --work work/run_nb --reports work/rep_nb --export-dir work/exp_nb` cho kết quả **Rework**, mã thoát **20**, còn 6 lỗi bắt buộc và `work/exp_nb/clean_v1` không tồn tại. Như vậy gate chặn xuất bản khi chưa có người review.

Ba ví dụ kiểm tra trực quan trong lô:

- `img_0001`: dòng 3 trùng box person dòng 1, IoU 0.9945; máy bỏ dòng trùng sau.
- `img_0004`: file nhãn rỗng nhưng ảnh có một phần xe trắng; không thể mặc định đây là ảnh nền, cần người gán/xác nhận nhãn.
- `img_0030`: dòng 9 vượt mép trái 0.022998 theo tỷ lệ ảnh. Autofix cắt box từ `(cx=-0.003833, w=0.038330)` thành `(cx=0.007666, w=0.015332)`; người cần xác nhận phần box còn lại vẫn mô tả đúng vật.

Hai loại lỗi còn lọt được đo trên calibration: `POSSIBLE_LOOSE_BOX` bỏ sót 4/5 ca (recall 0.20); `POSSIBLE_WRONG_CLASS` bỏ sót 1/6 ca (recall 0.83). Ngoài ra pHash bỏ sót 2/6 near-duplicate. Model không phải đáp án chuẩn: `POSSIBLE_FALSE_POS` có 5 TP/9 FP (precision 0.36), nên không tự xóa nhãn theo cảnh báo.

## 5. Train: raw vs clean

Đã train hai biến thể với 2 seed (0, 1), cùng YOLO26n pretrained, 15 epoch, batch 8, ảnh 416 px, CPU; dùng cùng val 40 ảnh và test 100 ảnh (387 instances). Đây là cấu hình CPU rút gọn theo `docs/COLAB.md`, không tương đương lượt Colab T4 20 epoch. Raw có 224 ảnh train; clean có 202 ảnh train theo manifest Hold.

Kết quả test, tổng hợp bởi `python scripts/summarize_results.py` (độ lệch chuẩn mẫu giữa 2 seed):

| Biến thể | Seed 0 mAP50 / mAP50-95 / P / R | Seed 1 mAP50 / mAP50-95 / P / R | TB ± SD: mAP50 | TB ± SD: mAP50-95 | TB ± SD: precision | TB ± SD: recall |
|---|---|---|---:|---:|---:|---:|
| Raw (224 ảnh) | 0.6416 / 0.4267 / 0.7523 / 0.5301 | 0.5825 / 0.3882 / 0.5641 / 0.5701 | 0.612 ± 0.042 | 0.407 ± 0.027 | 0.658 ± 0.133 | 0.550 ± 0.028 |
| Clean (202 ảnh) | 0.5497 / 0.3587 / 0.6684 / 0.4827 | 0.6352 / 0.4271 / 0.7405 / 0.4959 | 0.592 ± 0.060 | 0.393 ± 0.048 | 0.704 ± 0.051 | 0.489 ± 0.009 |

Chênh lệch trung bình clean − raw: mAP50 **−0.020**, mAP50-95 **−0.015**, precision **+0.046**, recall **−0.061**. Hai chỉ số mAP thấp hơn một ít; mức chênh nhỏ hơn độ lệch seed quan sát được ở mAP50 và mAP50-95. Precision tăng nhưng recall giảm. Với chỉ 2 seed, độ lệch chuẩn còn ước lượng kém; không đủ cơ sở kết luận clean tốt hơn hoặc raw tốt hơn. Đặc biệt, raw_seed0, raw_seed1 và clean_seed0 chạy ở Python 3.15.2 / Ultralytics 8.4.211; clean_seed1 được tiếp tục trong `.venv` ở Python 3.12.10 / Ultralytics 8.4.214 theo phiên bản repo pin. Các lần chạy có cùng model, torch 2.15.0 CPU, seed, epoch, batch, imgsz và split, nhưng khác phiên bản Python/Ultralytics là hạn chế về tính đồng nhất cần ghi nhận.

Hai giả thuyết và cách kiểm tiếp:

1. Clean giảm số ảnh train từ 224 xuống 202; loại ảnh trùng, lỗi và ảnh bị chặn có thể làm thay đổi lượng dữ liệu hoặc phân bố lớp, trong khi nhãn được sửa có thể giảm nhiễu. Kiểm bằng bảng số ảnh/instance theo lớp trước–sau, kiểm tra thủ công các ảnh bị loại và chạy ablation trên cùng tập ảnh, chỉ thay nhãn.
2. Tập clean vẫn ở trạng thái Hold với cảnh báo ngữ nghĩa chưa duyệt trên 29/202 ảnh; nhãn thiếu/lỏng hoặc các lớp ít mẫu có thể làm recall và AP dao động. Kiểm bằng adjudication một tập nhỏ có ground truth, xem lỗi dự đoán theo lớp, rồi chạy thêm seed (ít nhất 5) và bootstrap trên cùng test set.

Kết luận hiện tại: kết quả clean thể hiện trade-off precision/recall, chưa chứng minh cải thiện tổng thể; quyết định QC vẫn là **Hold**. Việc tiếp theo là chạy lại đủ bốn lượt trong cùng một môi trường (ưu tiên Colab T4 với cấu hình chuẩn), mở rộng seed và kiểm tra phân bố/lỗi theo lớp trước khi cân nhắc thay đổi ngưỡng pipeline.

## 6. Quyết định và ghi chú AI

- **Quyết định:** giữ **Hold**. Release đòi hỏi 0 lỗi bắt buộc và tối đa 20/202 ảnh còn cảnh báo chưa xử lý. Tiếp tục cải thiện độ chính xác công cụ/nhãn và thứ tự ưu tiên trong quy tắc cho phép, rồi đánh giá lại; ngân sách mỗi lượt vẫn tối đa 80 ảnh, không cộng thêm lượt duyệt để lách budget.
- **Prompt chính:** dùng docstring + test của từng module làm đặc tả: đầu vào YOLO `id cx cy w h`, trả `Issue`/log/verdict, ngưỡng đọc từ config; checks chỉ đọc, autofix sửa bản sao `ds`, không sửa test/raw hoặc đoán nhãn ngữ nghĩa.
- **Cách kiểm:** rà chỗ ghi/xóa, không `except: pass`, không viết cứng ngưỡng; chạy unit test, calibration và pipeline trên bản sao. `scripts/verify_edge_cases.py` kiểm thêm 7 ca tự tạo, gồm dòng hai lỗi, dòng trống, nhiều prediction; trước sửa 5/7 đạt, sau sửa 7/7 đạt. Gate budget 0 trả 20 và không export.
- **Lỗi AI đã sửa:** `second_opinion` bỏ qua prediction rỗng nên mất cảnh báo false positive; đã phân biệt entry rỗng với thiếu entry. `autofix` làm tròn chiều rộng giao khoảng `1e-7` thành 0; đã giữ độ chính xác float khi ghi box và kiểm QC lại không sinh lỗi bắt buộc mới.

Kiểm chứng cuối: **79 test đạt**, 7/7 ca biên đạt, 202 nhãn export khớp hash manifest; hai lượt pipeline cho cùng báo cáo/manifest (trừ thời gian và đường dẫn xuất). Sau khi hoàn tất train và tạo `comparison.md`, runner `python -X utf8 scripts/check_core_windows.py` chạy đầy đủ (cả train) báo **79 passed, 0 lỗi, 0 cảnh báo**. Checker gốc trên Windows có lỗi so dấu `\\` với `/`, quét nhầm file calibration; runner chỉ chuẩn hóa đường dẫn trong bộ nhớ, giữ nguyên checker và 32 file protected (xem `docs/WINDOWS_CHECK.md`). Checker đầy đủ được chạy với `.venv` Python 3.12.10; các lượt train có khác biệt phiên bản môi trường đã ghi tại §5.
