from config import CFG
# tests/test_ai_exploratory.py
#
# FIXES:
# 1. perform_action() was called but never defined — caused NameError.
# 2. detect_bug() was called but never imported — caused NameError.
# 3. save_bug_report() called with keyword args that don't match signature.
# 4. ask_ai() was called with a tuple (page_info) instead of unpacked args.
# 5. Added @allure decorators for report visibility.
# 6. Added element_ranker import (file now exists).

import allure
import pytest
from ai.ai_client import ask_ai
from ai.bug_detector import detect_bug
from ai.parser import parse_ai_action
from browser.dom_extractor import extract_page_info, extract_clickable_elements
from browser.element_ranker import rank_elements
from browser.screenshot import capture_bug_screenshot
from browser.validator import validate_target
from reporting.bug_reporter import save_bug_report, generate_bug_report


def _perform_action(page, action: str, target: str | None):
    """Execute a parsed AI action on the page."""
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
@allure.title("AI Exploratory Test — example.com")
def test_ai_exploration(page):

    with allure.step("Navigate to target"):
        page.goto(CFG.target_urls[0])
        allure.attach(page.url, name="Start URL",
                      attachment_type=allure.attachment_type.TEXT)

    for step in range(5):
        with allure.step(f"Exploration step {step + 1}"):

            # Extract & rank elements
            with allure.step("Extract and rank DOM elements"):
                page_text, buttons, links, inputs = extract_page_info(page)
                raw_elements = extract_clickable_elements(page)
                ranked = rank_elements(raw_elements)
                allure.attach(
                    str(ranked[:10]),
                    name="Top Ranked Elements",
                    attachment_type=allure.attachment_type.TEXT,
                )

            # AI decides next action
            with allure.step("AI decision"):
                ai_output = ask_ai(page_text, buttons, links, inputs)
                action, target = parse_ai_action(ai_output)
                allure.attach(
                    f"action={action}  target={target}",
                    name="AI Decision",
                    attachment_type=allure.attachment_type.TEXT,
                )

            # Capture before-state
            before_text, *_ = extract_page_info(page)

            # Execute action
            with allure.step(f"Perform action: {action}"):
                _perform_action(page, action, target)

            # Capture after-state and detect bugs
            with allure.step("Bug detection after action"):
                after_text, *_ = extract_page_info(page)
                bug_result = detect_bug(after_text)

                if "NO BUG" not in bug_result.upper():
                    with allure.step("🐛 Bug found — saving report"):
                        ss_path = capture_bug_screenshot(page, label=f"explore_bug_step{step+1}")
                        bug_report = generate_bug_report(
                            bug_result, after_text, allure_attach=True
                        )
                        bug_report["screenshot"] = ss_path
                        save_bug_report(bug_report)

                        if ss_path:
                            with open(ss_path, "rb") as f:
                                allure.attach(f.read(), name="Bug Screenshot",
                                              attachment_type=allure.attachment_type.PNG)

            if action == "stop" or action is None:
                with allure.step("Agent chose to stop"):
                    break

    assert page.title() is not None, "Page became unresponsive"
