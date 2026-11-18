#!/usr/bin/env python3
"""Run the supplied submission checker with its Windows path comparison fixed.

Usage: python scripts/check_core_windows.py --no-train

The original checker still reports false positives on Windows: its protected-file
keys use '/', while str(Path.relative_to(...)) uses '\\'. This runner replaces
only that comparison in memory. It leaves the checker, protected manifest,
tests, and data unchanged, and keeps every original validation. Arguments pass
through unchanged; omitting --no-train also runs the original training checks.
"""
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


def main():
    checker = Path(__file__).resolve().with_name("check_submission.py")
    source = checker.read_text(encoding="utf-8")
    original = "str(p.relative_to(ROOT))"
    replacement = "p.relative_to(ROOT).as_posix()"
    if source.count(original) != 1:
        raise SystemExit(
            "Checker source changed: expected exactly one protected-path "
            "comparison. Review this compatibility runner before using it."
        )

    if os.name == "nt":
        source = source.replace(original, replacement, 1)
        print(
            "Windows compatibility: normalize the protected-path comparison "
            "with as_posix() in memory; all original checks remain enabled.",
            flush=True,
        )

    # pytest parses PYTEST_ADDOPTS with shlex too. Quoting preserves Windows
    # paths containing spaces. These environment changes affect this process
    # and its checker subprocess only; existing options remain in the list.
    root = checker.parent.parent
    pytest_options = shlex.split(os.environ.get("PYTEST_ADDOPTS", ""))
    pytest_options.extend([
        "--ignore=work",
        f"--basetemp={root / 'work' / '.pytest-core-windows'}",
    ])
    os.environ["PYTEST_ADDOPTS"] = shlex.join(pytest_options)

    sys.argv[0] = str(checker)
    namespace = {
        "__name__": "__main__",
        "__file__": str(checker),
        "__package__": None,
        "__cached__": None,
    }
    exec(compile(source, str(checker), "exec"), namespace)


if __name__ == "__main__":
    main()
