# Kiểm tra bài nộp trên Windows

Checker gốc `scripts/check_submission.py` so đường dẫn `str(p.relative_to(ROOT))`
với khóa trong `scripts/_protected.json`. Windows tạo dấu `\`, còn manifest dùng
dấu `/`; vì vậy checker không nhận ra các file có sẵn và quét nhầm
`pipeline/calibrate.py`. Hai lỗi về `MANIFEST` và `data/calib` là báo nhầm do
đường dẫn này. File calibration vẫn khớp hash của bản đề.

Giữ nguyên checker gốc và manifest protected. Chạy runner tương thích từ thư mục
gốc repo:

```powershell
python -X utf8 scripts/check_core_windows.py --no-train
```

Runner công khai thay duy nhất biểu thức so đường dẫn thành
`p.relative_to(ROOT).as_posix()` trong bộ nhớ khi chạy trên Windows. Mọi kiểm tra
gốc về test, hash file protected, cấu hình, báo cáo và export vẫn được thực thi.
Đây là runner tương thích cục bộ; lệnh checker gốc trên Windows vẫn có thể báo
hai lỗi nêu trên. Kết quả chính thức do checker của giảng viên quyết định.

Runner giữ các tùy chọn `PYTEST_ADDOPTS` hiện có, thêm `--ignore=work` để không
thu thập thư mục làm việc tạm và đặt `--basetemp` trong
`work/.pytest-core-windows`. Test chính thức trong `tests/` vẫn chạy. Tùy chọn
chỉ áp dụng trong tiến trình runner; không cần đổi quyền thư mục Temp của hệ
thống hay sửa test.

`--no-train` chỉ bỏ qua phần kiểm kết quả train tùy chọn. Bỏ đối số này khi đã
train để chạy kiểm tra đầy đủ. Theo [RUBRIC.md](../RUBRIC.md), phần train có 15
điểm; chưa làm phần này thì tối đa 85/100 theo rubric.

Dự án nêu Python 3.9–3.13 trong [SETUP.md](SETUP.md). Môi trường hiện tại là
Python 3.15.2; lượt chạy trước đạt 79 test không đảm bảo tương thích trên mọi
phiên bản. Khi tái lập hoặc nộp bài, nên dùng một phiên bản trong dải dự án hỗ trợ.

Nhãn export được đánh dấu `-text` trong `.gitattributes` để Git giữ nguyên byte
khi add/clone. Manifest lưu SHA1 của byte nhãn; tự chuyển LF/CRLF sẽ làm hash
không khớp dù tọa độ box không đổi.
