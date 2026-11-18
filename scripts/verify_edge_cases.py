"""Kiểm tra các ca biên bằng dữ liệu giả; không đọc hay sửa dữ liệu lab.

Chạy từ thư mục repo: python -X utf8 scripts/verify_edge_cases.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.checks import label_format, second_opinion  # noqa: E402
from pipeline.common import ERROR, WARN, Dataset, Issue, load_config, parse_yolo_line  # noqa: E402
from pipeline.steps import autofix  # noqa: E402


CAR = "0 0.5 0.5 0.3 0.4"


def make_dataset(root, name, cfg, lines):
    ds_root = root / name
    (ds_root / "images").mkdir(parents=True)
    (ds_root / "labels").mkdir()
    Image.new("RGB", (640, 480), "white").save(ds_root / "images/a.png")
    (ds_root / "labels/a.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ds_root / "data.yaml").write_text(
        "names: [car, person, truck, bus]\n", encoding="utf-8"
    )
    return Dataset(ds_root, cfg["classes"])


def error(code, line):
    return Issue("synthetic", ERROR, code, "a", "ca giả lập", line)


def empty_predictions(root, cfg):
    ds = make_dataset(root, "empty_predictions", cfg, [CAR, "", "1 .1 .1 .1 .1"])
    got = second_opinion.run(ds, cfg, preds={"a": []})
    assert [(i.code, i.line) for i in got] == [
        ("POSSIBLE_FALSE_POS", 1), ("POSSIBLE_FALSE_POS", 3)
    ], "Prediction rỗng phải cảnh báo từng box nhãn với số dòng gốc"
    assert all(i.severity == WARN for i in got)


def absent_predictions(root, cfg):
    ds = make_dataset(root, "absent_predictions", cfg, [CAR])
    assert second_opinion.run(ds, cfg, preds={}) == [], "Thiếu khóa ảnh trong cache phải bỏ qua"


def narrow_clip(root, cfg):
    ds = make_dataset(root, "narrow_clip", cfg, ["1 -0.0999999 0.5 0.2 0.2"])
    issues = label_format.run(ds, cfg)
    assert any(i.code == "BOX_OUT_OF_IMAGE" for i in issues)
    fixes = autofix.fix(ds, issues, cfg)
    remaining = ds.read_label_lines("a")
    assert remaining and len(remaining) == 1, "Phần giao còn diện tích phải được giữ"
    _, cx, cy, width, height = parse_yolo_line(remaining[0][1])
    assert width > 0 and height > 0, "Làm tròn sau clip không được tạo BOX_ZERO"
    assert abs(width - 0.0000001) < 1e-12, "Chiều rộng phải bằng phần giao thực tế"
    assert cx - width / 2 >= -1e-12 and cy - height / 2 >= -1e-12
    assert cx + width / 2 <= 1 + 1e-12 and cy + height / 2 <= 1 + 1e-12
    assert [f["action"] for f in fixes] == ["clip_box"]
    second_qc = label_format.run(ds, cfg)
    assert not any(i.severity == ERROR for i in second_qc)
    assert autofix.fix(ds, second_qc, cfg) == [], "QC lại rồi autofix phải không sửa thêm"


def drop_wins(root, cfg):
    ds = make_dataset(root, "drop_wins", cfg, [CAR, "", "1 .95 .5 .2 .2", "0 .1 .1 .1 .1"])
    fixes = autofix.fix(ds, [error("BOX_OUT_OF_IMAGE", 3), error("DUP_BOX", 3)], cfg)
    assert ds.label_path("a").read_text(encoding="utf-8").splitlines() == [
        CAR, "", "0 .1 .1 .1 .1"
    ], "Xóa phải thắng clip và chỉ tác động dòng gốc được chỉ định"
    assert [(f["line"], f["action"]) for f in fixes] == [(3, "drop_line")]


def original_numbering(root, cfg):
    ds = make_dataset(root, "original_numbering", cfg, [CAR, "", "93 .5 .5 .2 .2", "0 .1 .1 .1 .1"])
    issues = label_format.run(ds, cfg)
    assert [(i.code, i.line) for i in issues if i.severity == ERROR] == [("BAD_CLASS_ID", 3)]
    fixes = autofix.fix(ds, issues, cfg)
    assert ds.label_path("a").read_text(encoding="utf-8").splitlines() == [
        CAR, "", "0 .1 .1 .1 .1"
    ]
    assert [(f["line"], f["action"]) for f in fixes] == [(3, "drop_line")]


def prediction_order(root, cfg):
    ds = make_dataset(root, "prediction_order", cfg, [CAR])
    preds = {"a": [
        [0, .95, .5, .5, .3, .4],
        [1, .91, .1, .2, .1, .2],
        [2, .92, .85, .7, .1, .2],
    ]}
    issues = second_opinion.run(ds, cfg, preds=preds)
    assert [(i.code, i.line, i.extra["conf"]) for i in issues] == [
        ("POSSIBLE_MISSING", None, .91), ("POSSIBLE_MISSING", None, .92)
    ], "Mỗi prediction sinh tối đa một issue theo thứ tự cache"


def warning_preserves_files(root, cfg):
    ds = make_dataset(root, "warning_preserves_files", cfg, ["1 .5 .5 .001 .001"])
    before = {p.relative_to(ds.root): p.read_bytes() for p in ds.root.rglob("*") if p.is_file()}
    warnings = label_format.run(ds, cfg)
    assert [i.code for i in warnings] == ["BOX_TINY"]
    assert second_opinion.run(ds, cfg, preds={"a": [[1, .95, .5, .5, .001, .001]]}) == []
    assert autofix.fix(ds, warnings, cfg) == [], "Autofix không xử lý WARN"
    after = {p.relative_to(ds.root): p.read_bytes() for p in ds.root.rglob("*") if p.is_file()}
    assert before == after, "Check và autofix WARN phải giữ nguyên mọi byte của dữ liệu giả"


def main():
    cfg = load_config(ROOT / "configs/pipeline.yaml")
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    cases = [
        empty_predictions, absent_predictions, narrow_clip, drop_wins,
        original_numbering, prediction_order, warning_preserves_files,
    ]
    failures = []
    with tempfile.TemporaryDirectory(prefix="verify_edges_", dir=work) as scratch:
        for case in cases:
            try:
                case(Path(scratch), cfg)
            except Exception as exc:
                failures.append(case.__name__)
                print(f"FAIL {case.__name__}: {type(exc).__name__}: {exc}")
            else:
                print(f"PASS {case.__name__}")
    print(f"Kết quả: {len(cases) - len(failures)}/{len(cases)} ca đạt; {len(failures)} ca lỗi")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
