# agents/agent_controller.py
import allure
from playwright.sync_api import Playwright
from config import CFG
from agents.ai_agent_worker import run_agent


@allure.feature("AI Autonomous Website Testing")
@allure.story("Multi-agent execution controller")
def start_agents(playwright: Playwright):
    """
    playwright: the Playwright instance from pytest-playwright's fixture.
    Passed through so run_agent() never calls sync_playwright() itself.
    """
    urls = CFG.target_urls

    allure.attach("\n".join(urls), name="Target URLs",
                  attachment_type=allure.attachment_type.TEXT)
    allure.attach(CFG.summary(), name="⚙ Active Configuration",
                  attachment_type=allure.attachment_type.TEXT)

    for i, url in enumerate(urls):
        agent_id = f"Agent-{i + 1}"
        with allure.step(f"Agent {i + 1} of {len(urls)}: {url}"):
            run_agent(playwright, url, agent_id)

    allure.attach(f"All {len(urls)} agent(s) finished.",
                  name="Controller Summary",
                  attachment_type=allure.attachment_type.TEXT)
