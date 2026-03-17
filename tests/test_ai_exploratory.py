# tests/test_ai_exploratory.py
#
# PHASE 1 UPDATE:
# - Uses _safe_goto() for timeout-resistant navigation
# - Calls login_if_needed() after navigation
# - Passes screenshot to detect_bug() for visual analysis
# - Shows detection source (visual/text) in Allure

import allure
import pytest
import os
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from ai.ai_client import ask_ai
from ai.bug_detector import detect_bug, collect_page_signals
from ai.parser import parse_ai_action
from browser.dom_extractor import extract_page_info, extract_clickable_elements
from browser.element_ranker import rank_elements
from browser.screenshot import capture_bug_screenshot, capture_step_screenshot
from browser.validator import validate_target
from browser.login_handler import login_if_needed
from reporting.bug_reporter import save_bug_report, generate_bug_report
from config import CFG


def _safe_goto(page, url: str):
    """Navigation with multiple fallback strategies."""
    for wait_until, timeout in [
        ("domcontentloaded", CFG.page_timeout),
        ("commit",           CFG.page_timeout),
        ("domcontentloaded", CFG.page_timeout * 2),
    ]:
        try:
            page.goto(url, wait_until=wait_until, timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            continue
        except Exception:
            break
    return False


def _safe_attach_screenshot(ss_path: str, name: str):
    if ss_path and os.path.exists(ss_path):
        try:
            with open(ss_path, "rb") as f:
                allure.attach(f.read(), name=name,
                              attachment_type=allure.attachment_type.PNG)
        except Exception:
            pass


def _perform_action(page, action: str, target: str | None):
    if action == "click" and target:
        if validate_target(page, target):
            page.click(f"text={target}", timeout=5000)
    elif action == "type":
        page.fill("input:visible", "testdata")
    elif action == "scroll":
        page.evaluate("window.scrollBy(0, 400)")


@allure.feature("AI Exploratory Testing")
@allure.story("Autonomous exploration with bug detection")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("AI Exploratory Test")
def test_ai_exploration(page):

    with allure.step("Navigate to target"):
        loaded = _safe_goto(page, CFG.target_urls[0])
        allure.attach(
            f"URL: {CFG.target_urls[0]}\nLoaded: {loaded}\nCurrent: {page.url}",
            name="Navigation Result",
            attachment_type=allure.attachment_type.TEXT,
        )

    # Smart login
    with allure.step("Smart Login Check"):
        login_result = login_if_needed(page)
        if login_result.get("attempted"):
            status = "SUCCESS" if login_result["success"] else "FAILED"
            login_ss = capture_step_screenshot(page, "exploratory_after_login")
            _safe_attach_screenshot(login_ss, f"After Login ({status})")

    for step in range(5):
        with allure.step(f"Exploration step {step + 1}"):

            with allure.step("Extract and rank DOM elements"):
                page_text, buttons, links, inputs = extract_page_info(page)
                raw_elements = extract_clickable_elements(page)
                ranked = rank_elements(raw_elements)
                allure.attach(
                    str(ranked[:10]),
                    name="Top Ranked Elements",
                    attachment_type=allure.attachment_type.TEXT,
                )

            with allure.step("AI decision"):
                ai_output = ask_ai(page_text, buttons, links, inputs)
                action, target = parse_ai_action(ai_output)
                allure.attach(
                    f"action={action}  target={target}",
                    name="AI Decision",
                    attachment_type=allure.attachment_type.TEXT,
                )

            before_text, *_ = extract_page_info(page)

            with allure.step(f"Perform action: {action}"):
                _perform_action(page, action, target)

            # Take screenshot for visual analysis
            ss_path = capture_step_screenshot(page, f"exploratory_step{step+1}")
            _safe_attach_screenshot(ss_path, f"Step {step+1} Screenshot")

            with allure.step("Bug detection (visual + text)"):
                after_text, *_ = extract_page_info(page)
                signals   = collect_page_signals(page)

                # Pass screenshot for visual analysis via llava
                bug_result = detect_bug(
                    after_text,
                    page_signals=signals,
                    screenshot_path=ss_path,
                )

                source = bug_result.get("source", "text")
                allure.attach(
                    f"Detection source: {source}\n"
                    f"Found: {bug_result.get('found')}\n"
                    f"Severity: {bug_result.get('severity')}\n"
                    f"Title: {bug_result.get('title')}",
                    name=f"Bug Detection ({source})",
                    attachment_type=allure.attachment_type.TEXT,
                )

                if bug_result.get("found", False):
                    with allure.step(f"Bug [{source}]: {bug_result.get('title')}"):
                        bug_ss = capture_bug_screenshot(
                            page, label=f"explore_bug_step{step+1}")
                        bug_result["screenshot"] = bug_ss
                        bug_report = generate_bug_report(
                            bug_result, after_text, allure_attach=True
                        )
                        save_bug_report(bug_report)
                        _safe_attach_screenshot(bug_ss, "Bug Screenshot")

            if action == "stop" or action is None:
                with allure.step("Agent chose to stop"):
                    break

    assert page.title() is not None, "Page became unresponsive"
