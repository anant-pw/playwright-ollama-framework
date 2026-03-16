# run_agents.py — Main entry point
#
# FIX: "Playwright Sync API inside the asyncio loop" error
# ─────────────────────────────────────────────────────────
# pytest-playwright runs an asyncio event loop for the test session.
# Calling sync_playwright() inside that loop raises:
#   "It looks like you are using Playwright Sync API inside the asyncio loop."
#
# The fix: accept the 'playwright' fixture that pytest-playwright already
# provides and manages correctly. Pass it into run_agent() so it uses the
# existing managed Playwright instance instead of creating a new one.

import allure
from playwright.sync_api import Playwright
from agents.agent_controller import start_agents
from reporting.test_reporter import init_report, close_report


@allure.feature("AI Autonomous Website Testing")
@allure.story("Full agent run")
@allure.severity(allure.severity_level.CRITICAL)
def test_run_ai_agents(playwright: Playwright):
    """
    Accept pytest-playwright's 'playwright' fixture — this is a Playwright
    instance that is already correctly managed outside the asyncio loop.
    We pass it into the agent so it never calls sync_playwright() itself.
    """
    init_report()
    try:
        start_agents(playwright)
    finally:
        close_report()
