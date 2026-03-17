# brain/action_executor.py
#
# PHASE 1 UPGRADE: Self-Healing Actions with Rich Allure Reporting
# ────────────────────────────────────────────────────────────────
# Every healing attempt is logged in a dedicated Allure step showing:
#   - Which strategies were tried
#   - Which failed and why
#   - Which one succeeded
#   - Total healing attempts needed
#
# This makes it easy to see in Allure exactly what the agent did
# to recover from a broken/moved/missing element.

import allure
import time
import json
from datetime import datetime
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

_CLICK_TIMEOUT = 4000
_FILL_TIMEOUT  = 4000


def execute_action(page: Page, decision: str) -> str:
    """
    Execute the AI decision on the page with self-healing retry logic.
    Decision format: "action_type:target_text"
    """
    decision = (decision or "stop").strip()
    action   = decision.split(":")[0].lower().strip()
    target   = decision[len(action)+1:].strip() if ":" in decision else ""

    attempts = []  # Full healing log with timestamps

    try:
        if action == "click_button":
            return _heal_click(page, "button", target, attempts)

        if action == "click_link":
            return _heal_click(page, "a", target, attempts)

        if action == "type_input":
            parts = target.split(":", 1)
            if len(parts) == 2:
                field_hint, value = parts[0].strip(), parts[1].strip()
            else:
                field_hint, value = target, "test_value"
            return _heal_fill(page, field_hint, value, attempts)

        if action == "scroll":
            amount = int(target) if target.isdigit() else 400
            page.evaluate(f"window.scrollBy(0, {amount})")
            _attach_healing_report(attempts, action, target, f"scrolled {amount}px", trivial=True)
            return f"scrolled down {amount}px"

        if action == "navigate":
            if target.startswith("http"):
                page.goto(target, wait_until="domcontentloaded", timeout=30_000)
                _attach_healing_report(attempts, action, target, f"navigated to {target}", trivial=True)
                return f"navigated to {target}"
            return "navigate: no valid URL"

    except Exception as e:
        _record(attempts, "exception", "FAILED", str(e))
        _attach_healing_report(attempts, action, target, None)
        return f"action failed ({action}:{target}): {e}"

    _attach_healing_report(attempts, action, target, None)
    return "stop"


# ── Self-healing click ────────────────────────────────────────────────────────

def _heal_click(page: Page, tag: str, target_text: str, attempts: list) -> str:
    """Try 5 strategies to click an element."""

    strategies = []
    if target_text:
        strategies = [
            ("1. Exact role match",    lambda: page.get_by_role(
                "button" if tag == "button" else "link",
                name=target_text, exact=True).first),
            ("2. Partial role match",  lambda: page.get_by_role(
                "button" if tag == "button" else "link",
                name=target_text, exact=False).first),
            ("3. Text contains",       lambda: page.locator(
                f"{tag}:visible", has_text=target_text).first),
            ("4. Case-insensitive text", lambda: page.locator(
                f"{tag}:visible >> text=/{target_text}/i").first),
            ("5. Any element with text", lambda: page.locator(
                ":visible", has_text=target_text).first),
        ]
    else:
        strategies = [
            ("1. First visible element", lambda: page.locator(f"{tag}:visible").first),
        ]

    strategies.append(
        (f"{len(strategies)+1}. Fallback: first visible {tag}",
         lambda: page.locator(f"{tag}:visible").first)
    )

    for strategy_name, get_locator in strategies:
        start = time.time()
        try:
            locator = get_locator()
            count   = locator.count()

            if count == 0:
                _record(attempts, strategy_name, "SKIPPED",
                        "0 elements found", elapsed=time.time()-start)
                continue

            el   = locator.first
            text = ""
            try:
                text = el.inner_text().strip()[:80]
            except Exception:
                pass

            el.scroll_into_view_if_needed(timeout=2000)
            el.click(timeout=_CLICK_TIMEOUT)

            result_msg = f"clicked {tag}: '{text}'"
            _record(attempts, strategy_name, "SUCCESS",
                    result_msg, elapsed=time.time()-start, element_text=text)
            _attach_healing_report(attempts, f"click_{tag}", target_text, result_msg)
            return result_msg

        except (PlaywrightTimeoutError, Exception) as e:
            err = str(e).split("\n")[0][:120]
            _record(attempts, strategy_name, "FAILED",
                    err, elapsed=time.time()-start)
            continue

    _attach_healing_report(attempts, f"click_{tag}", target_text, None)
    return f"no clickable {tag} found for '{target_text}'"


# ── Self-healing fill ─────────────────────────────────────────────────────────

def _heal_fill(page: Page, field_hint: str, value: str, attempts: list) -> str:
    """Try 6 strategies to fill an input field."""

    strategies = []
    if field_hint:
        strategies = [
            ("1. Placeholder match", lambda: page.get_by_placeholder(
                field_hint, exact=False).first),
            ("2. Label match",       lambda: page.get_by_label(
                field_hint, exact=False).first),
            ("3. name attribute",    lambda: page.locator(
                f"input[name*='{field_hint}']:visible").first),
            ("4. id attribute",      lambda: page.locator(
                f"input[id*='{field_hint}']:visible").first),
            ("5. aria-label",        lambda: page.locator(
                f"input[aria-label*='{field_hint}' i]:visible").first),
        ]

    strategies.append(
        (f"{len(strategies)+1}. Fallback: first visible input", lambda: page.locator(
            "input:visible:not([type=hidden])"
            ":not([type=checkbox]):not([type=radio])").first)
    )

    for strategy_name, get_locator in strategies:
        start = time.time()
        try:
            locator = get_locator()
            count   = locator.count()

            if count == 0:
                _record(attempts, strategy_name, "SKIPPED",
                        "0 elements found", elapsed=time.time()-start)
                continue

            inp = locator.first
            inp.scroll_into_view_if_needed(timeout=2000)
            inp.click(timeout=_FILL_TIMEOUT)
            inp.fill(value)

            result_msg = f"filled '{field_hint}' with '{value}'"
            _record(attempts, strategy_name, "SUCCESS",
                    result_msg, elapsed=time.time()-start)
            _attach_healing_report(attempts, "type_input", field_hint, result_msg)
            return result_msg

        except (PlaywrightTimeoutError, Exception) as e:
            err = str(e).split("\n")[0][:120]
            _record(attempts, strategy_name, "FAILED",
                    err, elapsed=time.time()-start)
            continue

    _attach_healing_report(attempts, "type_input", field_hint, None)
    return f"no fillable input found for '{field_hint}'"


# ── Healing record + Allure reporting ────────────────────────────────────────

def _record(attempts: list, strategy: str, status: str,
            detail: str = "", elapsed: float = 0, element_text: str = ""):
    """Record one healing attempt."""
    attempts.append({
        "strategy":     strategy,
        "status":       status,
        "detail":       detail,
        "elapsed_ms":   round(elapsed * 1000),
        "element_text": element_text,
        "timestamp":    datetime.now().strftime("%H:%M:%S.%f")[:-3],
    })
    icon = {"SUCCESS": "✅", "FAILED": "❌", "SKIPPED": "⏭"}.get(status, "•")
    print(f"[HEAL] {icon} {strategy}: {status} — {detail[:100]}")


def _attach_healing_report(attempts: list, action: str, target: str,
                           final_result: str | None, trivial: bool = False):
    """
    Attach a rich self-healing report to Allure.
    Only attaches if healing was actually needed (more than 1 attempt).
    """
    if not attempts:
        return

    failures  = [a for a in attempts if a["status"] == "FAILED"]
    skipped   = [a for a in attempts if a["status"] == "SKIPPED"]
    successes = [a for a in attempts if a["status"] == "SUCCESS"]

    # Don't clutter Allure if first attempt succeeded with no failures
    if trivial or (not failures and not skipped):
        return

    needed_healing = len(failures) > 0

    # ── Build text report ────────────────────────────────────────────────────
    lines = [
        f"Action:       {action}",
        f"Target:       '{target}'",
        f"Final result: {final_result or 'FAILED — no strategy worked'}",
        f"Needed healing: {'YES' if needed_healing else 'NO'}",
        f"Total strategies tried: {len(attempts)}",
        f"  Failures: {len(failures)}",
        f"  Skipped:  {len(skipped)}",
        f"  Success:  {len(successes)}",
        "",
        "─" * 60,
        "STRATEGY ATTEMPTS:",
        "─" * 60,
    ]

    for a in attempts:
        icon    = {"SUCCESS": "✅", "FAILED": "❌", "SKIPPED": "⏭"}.get(a["status"], "•")
        elapsed = f"({a['elapsed_ms']}ms)" if a["elapsed_ms"] else ""
        lines.append(f"  {icon} {a['strategy']:<35} {a['status']:<8} {elapsed}")
        if a["detail"]:
            # Wrap detail nicely
            detail_short = a["detail"][:100]
            lines.append(f"     └─ {detail_short}")
        if a["element_text"]:
            lines.append(f"     └─ Element text: '{a['element_text'][:60]}'")

    if needed_healing:
        lines += [
            "",
            "─" * 60,
            "HEALING SUMMARY:",
            f"  The agent tried {len(failures)} strateg{'y' if len(failures)==1 else 'ies'} before finding a working one.",
            f"  This means the element '{target}' was not found by its expected selector",
            f"  but the agent automatically recovered using a fallback strategy.",
            "─" * 60,
        ]

    report_text = "\n".join(lines)

    # ── Build JSON report (for download in Allure) ───────────────────────────
    report_json = {
        "action":         action,
        "target":         target,
        "final_result":   final_result,
        "needed_healing": needed_healing,
        "total_attempts": len(attempts),
        "failures":       len(failures),
        "attempts":       attempts,
    }

    # ── Attach to Allure ─────────────────────────────────────────────────────
    try:
        step_name = (
            f"Self-Healing: {action} '{target[:30]}' "
            f"({'RECOVERED after ' + str(len(failures)) + ' failures' if needed_healing else 'first try'})"
        )

        with allure.step(step_name):
            # Text summary (always shown)
            allure.attach(
                report_text,
                name=f"Healing Report: {action}",
                attachment_type=allure.attachment_type.TEXT,
            )

            # JSON details (downloadable)
            allure.attach(
                json.dumps(report_json, indent=2, default=str),
                name=f"Healing Details (JSON)",
                attachment_type=allure.attachment_type.JSON,
            )

            # Per-strategy breakdown as a CSV table
            csv_lines = ["Strategy,Status,Time(ms),Detail"]
            for a in attempts:
                detail_escaped = a["detail"].replace(",", ";").replace("\n", " ")[:80]
                csv_lines.append(
                    f"{a['strategy']},{a['status']},{a['elapsed_ms']},{detail_escaped}"
                )
            allure.attach(
                "\n".join(csv_lines),
                name="Strategy Breakdown",
                attachment_type=allure.attachment_type.CSV,
            )

    except Exception as e:
        print(f"[WARN] Could not attach healing report to Allure: {e}")
