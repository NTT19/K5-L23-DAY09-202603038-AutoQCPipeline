"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_codes = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    drop_lines = defaultdict(set)
    clip_lines = defaultdict(set)
    remove_images = set()
    needs_label = set()
    rename_classes = False

    for issue in issues:
        if issue.severity != ERROR:
            continue
        if issue.code == "BAD_CLASS_NAME" and issue.image == "data.yaml":
            rename_classes = True
        elif issue.code.startswith("DUP_IMAGE_") or issue.code in remove_codes:
            remove_images.add(issue.image)
        elif issue.code == "MISSING_LABEL_FILE":
            needs_label.add(issue.image)
        elif issue.code in drop_codes and issue.line is not None:
            drop_lines[issue.image].add(issue.line)
        elif issue.code == "BOX_OUT_OF_IMAGE" and issue.line is not None:
            clip_lines[issue.image].add(issue.line)

    fixes = []

    if rename_classes:
        try:
            old_data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            old_data = None
        data = old_data if isinstance(old_data, dict) else {}
        old_names = data.get("names", "(không đọc được)")
        data["names"] = list(cfg["classes"])
        ds.yaml_path.parent.mkdir(parents=True, exist_ok=True)
        ds.yaml_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        fixes.append({
            "image": "data.yaml", "line": None, "action": "rename_classes",
            "before": str(old_names), "after": str(cfg["classes"]),
        })

    for stem in sorted(remove_images):
        if stem == "data.yaml":
            continue
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)
        before = image_path.name if image_path is not None else "(không có ảnh)"
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        label_path.unlink(missing_ok=True)
        fixes.append({
            "image": stem, "line": None, "action": "remove_image",
            "before": before, "after": "đã loại ảnh và nhãn khỏi ds",
        })

    for stem in sorted(set(drop_lines) | set(clip_lines)):
        if stem in remove_images:
            continue
        label_path = ds.label_path(stem)
        if not label_path.exists():
            continue

        original = label_path.read_text(encoding="utf-8", errors="replace")
        original_lines = original.splitlines()
        trailing_newline = original.endswith(("\n", "\r"))
        removed = drop_lines.get(stem, set())
        clipped = clip_lines.get(stem, set()) - removed
        new_lines = []

        for line_no, text in enumerate(original_lines, 1):
            if line_no in removed:
                fixes.append({
                    "image": stem, "line": line_no, "action": "drop_line",
                    "before": text, "after": "",
                })
                continue

            if line_no not in clipped:
                new_lines.append(text)
                continue

            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError):
                # Dòng không parse được không thể cắt an toàn.
                fixes.append({
                    "image": stem, "line": line_no, "action": "drop_line",
                    "before": text, "after": "",
                })
                continue

            if width <= 0 or height <= 0:
                fixes.append({
                    "image": stem, "line": line_no, "action": "drop_line",
                    "before": text, "after": "",
                })
                continue

            left = max(0.0, cx - width / 2)
            top = max(0.0, cy - height / 2)
            right = min(1.0, cx + width / 2)
            bottom = min(1.0, cy + height / 2)
            if right <= left or bottom <= top:
                fixes.append({
                    "image": stem, "line": line_no, "action": "drop_line",
                    "before": text, "after": "",
                })
                continue

            new_cx = (left + right) / 2
            new_cy = (top + bottom) / 2
            new_width = right - left
            new_height = bottom - top
            # Giữ độ chính xác float: box còn giao rất mỏng không được làm tròn về 0.
            after = " ".join((
                str(class_id), f"{new_cx:.17g}", f"{new_cy:.17g}",
                f"{new_width:.17g}", f"{new_height:.17g}",
            ))
            new_lines.append(after)
            fixes.append({
                "image": stem, "line": line_no, "action": "clip_box",
                "before": text, "after": after,
            })

        updated = "\n".join(new_lines)
        if trailing_newline and new_lines:
            updated += "\n"
        if updated != original:
            label_path.write_text(updated, encoding="utf-8")

    for stem in sorted(needs_label - remove_images):
        fixes.append({
            "image": stem, "line": None, "action": "needs_label",
            "before": "(không có file)", "after": "chuyển người gán",
        })

    return fixes
