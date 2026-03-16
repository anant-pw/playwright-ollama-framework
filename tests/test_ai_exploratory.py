# tests/test_ai_exploratory.py
#
# FIXES:
# 1. detect_bug() now returns a DICT not a string — updated all checks
# 2. collect_page_signals() added — passes real browser signals to detect_bug()
# 3. Bug saving now uses dict directly instead of string .upper() check
# 4. generate_bug_report() receives the structured dict correctly

import allure
import pytest
from ai.ai_client import ask_ai
from ai.bug_detector import detect_bug, collect_page_signals
from ai.parser import parse_ai_action
from browser.dom_extractor import extract_page_info, extract_clickable_elements
from browser.element_ranker import rank_elements
from browser.screenshot import capture_bug_screenshot
from browser.validator import validate_target
from reporting.bug_reporter import save_bug_report, generate_bug_report
from config import CFG


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
@allure.title("AI Exploratory Test")
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

                # Collect real browser signals (console errors, failed requests etc.)
                signals = collect_page_signals(page)

                # detect_bug() returns a dict — NOT a string
                bug_result = detect_bug(after_text, page_signals=signals)

                allure.attach(
                    f"Found: {bug_result.get('found')} | "
                    f"Severity: {bug_result.get('severity')} | "
                    f"Title: {bug_result.get('title')}",
                    name="Bug Detection Summary",
                    attachment_type=allure.attachment_type.TEXT,
                )

                # Check the 'found' key — not .upper() on a string
                if bug_result.get("found", False):
                    with allure.step(f"Bug found: {bug_result.get('title', 'Unknown')}"):
                        ss_path = capture_bug_screenshot(
                            page, label=f"explore_bug_step{step + 1}"
                        )
                        # Attach screenshot path to bug result before saving
                        bug_result["screenshot"] = ss_path

                        # generate_bug_report accepts a dict directly
                        bug_report = generate_bug_report(
                            bug_result, after_text, allure_attach=True
                        )
                        save_bug_report(bug_report)

                        if ss_path:
                            try:
                                with open(ss_path, "rb") as f:
                                    allure.attach(
                                        f.read(),
                                        name="Bug Screenshot",
                                        attachment_type=allure.attachment_type.PNG,
                                    )
                            except Exception as e:
                                print(f"[WARN] Could not attach screenshot: {e}")

            if action == "stop" or action is None:
                with allure.step("Agent chose to stop"):
                    break

    assert page.title() is not None, "Page became unresponsive"
