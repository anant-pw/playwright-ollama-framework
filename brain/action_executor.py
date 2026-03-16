# brain/action_executor.py
#
# IMPROVEMENT: AI now tells us WHICH element to interact with, not just what type.
# Old version always clicked the FIRST visible button/link regardless.
# Now the decision engine returns "click_button:Sign In" and we find that specific element.

import allure
from playwright.sync_api import Page


def execute_action(page: Page, decision: str) -> str:
    """
    Execute the AI decision on the page.
    Decision format: "action_type:target_text"
    Examples:
      "click_button:Sign In"
      "click_link:Forgot password"
      "type_input:email:test@example.com"
      "scroll"
      "stop"
    """
    decision = decision.strip()
    action   = decision.split(":")[0].lower().strip()
    # Target is everything after the first colon
    target   = decision[len(action)+1:].strip() if ":" in decision else ""

    try:
        if action == "click_button":
            return _click_element(page, "button", target)

        if action == "click_link":
            return _click_element(page, "a", target)

        if action == "type_input":
            # format: "type_input:field_name:value"  or just "type_input:value"
            parts = target.split(":", 1)
            if len(parts) == 2:
                field_hint, value = parts[0].strip(), parts[1].strip()
            else:
                field_hint, value = target, "test_value"
            return _fill_input(page, field_hint, value)

        if action == "scroll":
            amount = int(target) if target.isdigit() else 400
            page.evaluate(f"window.scrollBy(0, {amount})")
            return f"scrolled down {amount}px"

        if action == "navigate":
            if target.startswith("http"):
                page.goto(target, wait_until="domcontentloaded", timeout=30_000)
                return f"navigated to {target}"
            return "navigate: no valid URL"

    except Exception as e:
        return f"action failed ({action}:{target}): {e}"

    return "stop"


def _click_element(page: Page, tag: str, target_text: str) -> str:
    """Click an element by text match, falling back to first visible."""
    # Try exact text match first
    if target_text:
        for locator in [
            page.get_by_role("button", name=target_text, exact=False),
            page.get_by_role("link",   name=target_text, exact=False),
            page.locator(f"{tag}:visible", has_text=target_text),
        ]:
            try:
                if locator.count() > 0:
                    el = locator.first
                    text = el.inner_text().strip()[:50]
                    el.click(timeout=5000)
                    return f"clicked {tag}: '{text}'"
            except Exception:
                continue

    # Fallback: first visible element of that tag
    try:
        el = page.locator(f"{tag}:visible").first
        if el.count():
            text = el.inner_text().strip()[:50]
            el.click(timeout=5000)
            return f"clicked first {tag}: '{text}'"
    except Exception as e:
        return f"no clickable {tag} found: {e}"

    return f"no visible {tag} found"


def _fill_input(page: Page, field_hint: str, value: str) -> str:
    """Fill an input field by placeholder/label/name match."""
    if field_hint:
        for locator in [
            page.get_by_placeholder(field_hint, exact=False),
            page.get_by_label(field_hint,       exact=False),
            page.locator(f"input[name*='{field_hint}']:visible"),
            page.locator(f"input[id*='{field_hint}']:visible"),
        ]:
            try:
                if locator.count() > 0:
                    locator.first.fill(value)
                    return f"filled '{field_hint}' with '{value}'"
            except Exception:
                continue

    # Fallback: first visible input that isn't hidden/checkbox/radio
    try:
        inp = page.locator(
            "input:visible:not([type=hidden]):not([type=checkbox]):not([type=radio])"
        ).first
        if inp.count():
            inp.fill(value)
            return f"filled first input with '{value}'"
    except Exception as e:
        return f"no fillable input found: {e}"

    return "no visible input found"
