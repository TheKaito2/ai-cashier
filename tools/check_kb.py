#!/usr/bin/env python3
"""Keep the knowledge base honest.

`docs/kb/` and `CLAUDE.md` refer to code as `path/to/file.py:symbol` - a
repository-relative path and, optionally, a symbol name.  Deliberately not a line
number: line numbers rot on the next edit, and a knowledge base that quietly
points at the wrong line is worse than one that admits it does not know.

This walks every reference and asserts the file still exists and the symbol still
appears in it, so a rename fails the test suite instead of misleading whoever
reads the page next.  Generated files that are gitignored (results, tables, the
graph) are skipped - they are absent in a fresh checkout by design.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "CLAUDE.md", *sorted((ROOT / "docs" / "kb").glob("*.md"))]

#: file kinds worth checking; anything else in backticks is prose or a command
SUFFIXES = ("py", "swift", "js", "css", "html", "tex", "bib", "json", "jsonc",
            "yml", "yaml", "csv", "md", "txt", "ps1", "iss", "service", "sh")

REFERENCE = re.compile(
    r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:" + "|".join(SUFFIXES) + r"))"
    r"(?::([A-Za-z0-9_.]+))?`"
)


def is_ignored(path: str) -> bool:
    """Generated files are absent in a clean checkout; that is not an error."""
    return subprocess.run(["git", "check-ignore", "-q", path],
                          cwd=ROOT, capture_output=True).returncode == 0


def check() -> tuple[int, list[str]]:
    checked, problems = 0, []
    for page in PAGES:
        if not page.exists():
            problems.append(f"{page.relative_to(ROOT)}: page is missing")
            continue
        for line_no, line in enumerate(page.read_text().splitlines(), 1):
            for path_str, symbol in REFERENCE.findall(line):
                where = f"{page.relative_to(ROOT)}:{line_no}"
                target = ROOT / path_str
                if not target.exists():
                    if not is_ignored(path_str):
                        problems.append(f"{where}: {path_str} does not exist")
                    continue
                checked += 1
                if symbol and symbol not in target.read_text(errors="ignore"):
                    problems.append(f"{where}: {path_str} no longer contains "
                                    f"'{symbol}'")
    return checked, problems


def main() -> int:
    checked, problems = check()
    for p in problems:
        print(f"  {p}")
    print(f"{checked} references checked across {len(PAGES)} pages, "
          f"{len(problems)} problem{'' if len(problems) == 1 else 's'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
