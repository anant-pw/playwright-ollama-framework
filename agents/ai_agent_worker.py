# agents/ai_agent_worker.py

import allure
from playwright.sync_api import Playwright
from config import CFG

from ai.bug_detector import detect_bug, collect_page_signals
from ai.ai_client import ask_ai
from ai.test_generator import generate_test_cases

from browser.dom_extractor import extract_page_info
from browser.screenshot import capture_bug_screenshot, capture_step_screenshot

from reporting.bug_reporter import save_bug_report, generate_bug_report
from reporting.test_reporter import log_test

from brain.decision_engine import decide_next_action
from brain.action_executor import execute_action
from brain.state_memory import StateMemory
from brain.exploration_tracker import ExplorationTracker


def run_agent(playwright: Playwright, start_url: str, agent_id: str):
    try:
        allure.dynamic.title(f"Agent: {agent_id} → {start_url}")
    except Exception:
        pass

    memory  = StateMemory()
    tracker = ExplorationTracker()

    with allure.step(f"[{agent_id}] Exploring {start_url}"):
        launcher = getattr(playwright, CFG.browser)
        browser  = launcher.launch(**CFG.browser_launch_kwargs())
        context  = browser.new_context(**CFG.browser_context_kwargs())

        # Capture console errors and network failures as real bug signals
        console_errors  = []
        failed_requests = []
        context.on("console",  lambda msg: console_errors.append(msg.text)
                   if msg.type == "error" else None)
        context.on("requestfailed", lambda req: failed_requests.append(
                   f"{req.method} {req.url} — {req.failure}"))

        page = context.new_page()

        try:
            with allure.step("Navigate to start URL"):
                page.goto(start_url, wait_until="domcontentloaded",
                          timeout=CFG.page_timeout)
                allure.attach(start_url, name="Start URL",
                              attachment_type=allure.attachment_type.TEXT)

            for step_num in range(1, CFG.max_steps + 1):
                with allure.step(f"Step {step_num} of {CFG.max_steps}"):
                    current_url = page.url
                    page_title  = ""
                    try:
                        page_title = page.title()
                    except Exception:
                        pass

                    # 1. Extract DOM
                    with allure.step("Extract DOM"):
                        page_text, buttons, links, inputs = extract_page_info(page)
                        allure.attach(page_text[:3000], name="Page Text",
                                      attachment_type=allure.attachment_type.TEXT)

                    # 2. Screenshot
                    with allure.step("Capture screenshot"):
                        ss_path = capture_step_screenshot(page, f"step_{step_num}")
                        if ss_path:
                            with open(ss_path, "rb") as f:
                                allure.attach(f.read(),
                                              name=f"Screenshot – Step {step_num}",
                                              attachment_type=allure.attachment_type.PNG)

                    # 3. Generate TCs — now passes actual page elements
                    with allure.step("Generate test cases"):
                        generate_test_cases(
                            page_text, current_url,
                            buttons=buttons, inputs=inputs, links=links,
                            page_title=page_title,
                        )

                    # 4. Bug Detection — now uses structured output + real signals
                    with allure.step("Bug detection"):
                        page_signals = collect_page_signals(page)
                        page_signals["console_errors"]  = list(console_errors)
                        page_signals["failed_requests"] = list(failed_requests)

                        bug = detect_bug(page_text, page_signals)

                        if bug.get("found"):
                            with allure.step(
                                f"🐛 [{bug['severity']}] {bug['title']}"
                            ):
                                bug_ss = capture_bug_screenshot(
                                    page, label=f"bug_step{step_num}")

                                bug_data = {
                                    "title":       bug["title"],
                                    "description": bug["description"],
                                    "severity":    bug["severity"],
                                    "steps":       [],
                                    "screenshot":  bug_ss,
                                    "additional_info": {
                                        "category":       bug.get("category"),
                                        "url":            current_url,
                                        "page_title":     page_title,
                                        "console_errors": console_errors[:5],
                                        "failed_requests": failed_requests[:5],
                                    }
                                }
                                bug_report = generate_bug_report(
                                    bug_data, page_text, allure_attach=True)
                                save_bug_report(bug_report)

                                if bug_ss:
                                    with open(bug_ss, "rb") as f:
                                        allure.attach(
                                            f.read(),
                                            name=f"Bug Screenshot – Step {step_num}",
                                            attachment_type=allure.attachment_type.PNG)

                    # 5. AI Decision — now returns specific element targets
                    with allure.step("AI decision"):
                        decision = decide_next_action(
                            page_text, buttons, links, inputs,
                            memory.history(),
                            page_title=page_title,
                            current_url=current_url,
                        )
                        allure.attach(decision, name="AI Decision",
                                      attachment_type=allure.attachment_type.TEXT)

                    # 6. Execute action
                    with allure.step(f"Execute: {decision}"):
                        action_result = execute_action(page, decision)
                        memory.add_action(f"Step {step_num}: {action_result}")
                        tracker.add(action_result, page.url)
                        allure.attach(action_result, name="Action Result",
                                      attachment_type=allure.attachment_type.TEXT)

                    # Clear per-step signals (keep only new ones next step)
                    console_errors.clear()
                    failed_requests.clear()

                    if "stop" in action_result.lower() or decision == "stop":
                        with allure.step("Agent chose to stop"):
                            pass
                        break

            tracker.attach_report()
            log_test(agent_id, start_url, "Exploratory Testing", "PASS")

        except Exception as e:
            with allure.step(f"❌ Exception: {e}"):
                err_ss = capture_bug_screenshot(page, label="exception")
                bug_report = generate_bug_report(str(e), "", allure_attach=True)
                bug_report["screenshot"] = err_ss
                save_bug_report(bug_report)
                if err_ss:
                    with open(err_ss, "rb") as f:
                        allure.attach(f.read(), name="Exception Screenshot",
                                      attachment_type=allure.attachment_type.PNG)
                log_test(agent_id, start_url, "Exploratory Testing", "FAIL")
                raise

        finally:
            with allure.step("Close browser"):
                page.close()
                context.close()
                browser.close()
