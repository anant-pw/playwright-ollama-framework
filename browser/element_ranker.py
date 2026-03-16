# browser/element_ranker.py
#
# NEW FILE — test_ai_exploratory.py imports this but it didn't exist,
# causing an ImportError at collection time that prevented ANY test from running.

from typing import Any


def rank_elements(elements: list[dict]) -> list[dict]:
    """
    Rank clickable elements by testing priority.
    Scoring heuristics (higher = more interesting to test):
      - Forms / inputs  → 3 pts
      - Buttons         → 2 pts
      - Links           → 1 pt
      - Has visible text → +1 pt
    Returns elements sorted highest score first.
    """
    def score(el: dict) -> int:
        tag  = (el.get("tag") or "").upper()
        text = (el.get("text") or "").strip()
        pts  = 0
        if tag == "INPUT":
            pts += 3
        elif tag == "BUTTON":
            pts += 2
        elif tag == "A":
            pts += 1
        if text:
            pts += 1
        return pts

    return sorted(elements, key=score, reverse=True)
