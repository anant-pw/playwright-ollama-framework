# browser/dom_extractor.py
#
# IMPROVEMENTS:
# 1. Added extract_clickable_elements() that test_ai_exploratory.py references.
# 2. Safe fallbacks — locator calls won't crash if page hasn't loaded.

from playwright.sync_api import Page


def extract_page_info(page: Page) -> tuple[str, list, list, list]:
    """Return (page_text, buttons, links, inputs)."""
    try:
        page_text = page.inner_text("body") or ""
    except Exception:
        page_text = ""

    try:
        buttons = page.locator("button").all_inner_texts()
    except Exception:
        buttons = []

    try:
        links = page.locator("a").all_inner_texts()
    except Exception:
        links = []

    try:
        inputs = page.locator("input").evaluate_all(
            "els => els.map(e => e.name || e.placeholder || e.id || 'unnamed')"
        )
    except Exception:
        inputs = []

    return page_text, buttons, links, inputs


def extract_clickable_elements(page: Page) -> list[dict]:
    """
    Return a list of dicts describing all clickable elements.
    Used by test_ai_exploratory.py and element_ranker.
    """
    try:
        elements = page.locator("button, a, input[type=submit], input[type=button]").all()
        result = []
        for el in elements:
            try:
                result.append({
                    "tag":  el.evaluate("e => e.tagName"),
                    "text": el.inner_text(),
                    "id":   el.get_attribute("id") or "",
                    "href": el.get_attribute("href") or "",
                })
            except Exception:
                pass
        return result
    except Exception:
        return []
