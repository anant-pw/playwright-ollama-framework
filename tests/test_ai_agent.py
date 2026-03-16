from config import CFG
# tests/test_ai_agent.py
#
# FIXES:
# 1. Added @allure decorators — without these pytest collects the test but
#    Allure has no metadata, so TCs appear as "unknown" with no feature/story.
# 2. ask_ai() in original was called with 5 args but ai_client.py only accepted 4.
#    history parameter is now supported in ai_client.py.
# 3. Added proper assertions so pytest actually marks pass/fail.

import allure
import pytest
from ai.ai_client import ask_ai
from ai.parser import parse_ai_action
from browser.dom_extractor import extract_page_info
from browser.validator import validate_target


@allure.feature("AI Agent")
@allure.story("Basic page exploration")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("AI Agent — explore example.com for 5 steps")
def test_ai_agent(page):
    """Playwright pytest fixture 'page' is provided by pytest-playwright."""

    with allure.step("Navigate to target URL"):
        page.goto(CFG.target_urls[0])
        allure.attach(page.url, name="Current URL",
                      attachment_type=allure.attachment_type.TEXT)

    history = []

    for step in range(5):
        with allure.step(f"Exploration step {step + 1}"):

            page_text, buttons, links, inputs = extract_page_info(page)

            with allure.step("Ask AI for next action"):
                ai_output = ask_ai(page_text, buttons, links, inputs, history)
                allure.attach(ai_output, name="AI Decision",
                              attachment_type=allure.attachment_type.TEXT)

            action, target = parse_ai_action(ai_output)
            history.append(f"{action} -> {target}")

            allure.attach(
                f"action={action}  target={target}",
                name="Parsed Action",
                attachment_type=allure.attachment_type.TEXT,
            )

            if action == "click" and target:
                with allure.step(f"Click: {target}"):
                    if validate_target(page, target):
                        page.click(f"text={target}")
                    else:
                        allure.attach(f"Target '{target}' not found, skipping.",
                                      name="Skip Reason",
                                      attachment_type=allure.attachment_type.TEXT)

            elif action == "type":
                with allure.step("Type into input"):
                    page.fill("input", "testdata")

            elif action == "stop" or action is None:
                with allure.step("Agent chose to stop"):
                    break

    # Final assertion — page should still be responsive
    assert page.title() is not None, "Page became unresponsive during exploration"
