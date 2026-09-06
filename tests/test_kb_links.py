"""The knowledge base has to stay true, and only a test can promise that.

`docs/kb/` and `CLAUDE.md` are the first thing anyone reads when they pick this
project up again.  Documentation that drifts is worse than none: it is confidently
wrong.  Every code reference on those pages names a file and, usually, a symbol,
so a rename that orphans one fails here rather than misleading the next reader.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_kb import PAGES, check  # noqa: E402


def test_every_knowledge_base_reference_still_resolves():
    checked, problems = check()
    assert not problems, "stale references in the knowledge base:\n  " + "\n  ".join(problems)
    assert checked > 100, f"only {checked} references found - has docs/kb/ emptied out?"


def test_every_page_exists_and_says_something():
    for page in PAGES:
        assert page.exists(), f"{page} is referenced as a knowledge base page but is missing"
        assert len(page.read_text().split()) > 50, f"{page} is a stub"


def test_the_index_reaches_every_page():
    index = (ROOT / "docs" / "kb" / "00-index.md").read_text()
    for page in sorted((ROOT / "docs" / "kb").glob("*.md")):
        if page.name == "00-index.md":
            continue
        assert page.name in index, f"{page.name} is not reachable from the index"
