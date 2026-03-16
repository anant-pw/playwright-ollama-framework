# agents/ai_agent_worker.py
#
# FIX 1: Screenshot FileNotFoundError — check if file exists before opening
# FIX 2: Page navigation uses networkidle fallback for slow/bot-protected sites
# FIX 3: Increased page timeout handling

import allure
from playwright.sync_api import Playwright, TimeoutError as PlaywrightTimeoutError
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


def _safe_goto(page, url: str, timeout: int):
    """
    Try multiple wait strategies for bot-protected / slow sites.
    Falls back gracefully instead of raising TimeoutError.
    """
    strategies = [
        ("domcontentloaded", timeout),
        ("commit",           timeout),
        ("domcontentloaded", timeout * 2),
    ]
    last_error = None
    for wait_until, t in strategies:
        try:
            page.goto(url, wait_until=wait_until, timeout=t)
            print(f"[NAV] Loaded {url} (wait={wait_until})")
            return True
        except PlaywrightTimeoutError as e:
            last_error = e
            print(f"[WARN] Timeout with wait={wait_until}, trying next strategy...")
        except Exception as e:
            last_error = e
            print(f"[WARN] Navigation error: {e}")
            break
    print(f"[ERROR] Could not load {url}: {last_error}")
    return False


def _safe_attach_screenshot(ss_path: str, name: str):
    """Attach screenshot to Allure only if the file actually exists."""
    if ss_path and isinstance(ss_path, str):
        try:
            import os
            if os.path.exists(ss_path):
                with open(ss_path, "rb") as f:
                    allure.attach(f.read(), name=name,
                                  attachment_type=allure.attachment_type.PNG)
            else:
                print(f"[WARN] Screenshot not found, skipping attach: {ss_path}")
        except Exception as e:
            print(f"[WARN] Could not attach screenshot: {e}")


def run_agent(playwright: Playwright, start_url: str, agent_id: str):
    try:
        allure.dynamic.title(f"Agent: {agent_id} -> {start_url}")
    except Exception:
        pass

    memory  = StateMemory()
    tracker = ExplorationTracker()

    with allure.step(f"[{agent_id}] Exploring {start_url}"):
        launcher = getattr(playwright, CFG.browser)
        browser  = launcher.launch(**CFG.browser_launch_kwargs())
        context  = browser.new_context(**CFG.browser_context_kwargs())

        console_errors  = []
        failed_requests = []
        context.on("console",  lambda msg: console_errors.append(msg.text)
                   if msg.type == "error" else None)
        context.on("requestfailed", lambda req: failed_requests.append(
                   f"{req.method} {req.url} - {req.failure}"))

        page = context.new_page()

        try:
            with allure.step("Navigate to start URL"):
                loaded = _safe_goto(page, start_url, CFG.page_timeout)
                if not loaded:
                    # Still try to work with whatever loaded
                    print(f"[WARN] Page may not have fully loaded, continuing anyway...")
                allure.attach(start_url, name="Start URL",
                              attachment_type=allure.attachment_type.TEXT)
                allure.attach(f"Page loaded: {loaded}\nCurrent URL: {page.url}",
                              name="Navigation Result",
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
                        try:
                            page_text, buttons, links, inputs = extract_page_info(page)
                        except Exception as e:
                            print(f"[WARN] DOM extraction failed: {e}")
                            page_text, buttons, links, inputs = "", [], [], []
                        allure.attach(page_text[:3000], name="Page Text",
                                      attachment_type=allure.attachment_type.TEXT)

                    # 2. Screenshot
                    with allure.step("Capture screenshot"):
                        ss_path = capture_step_screenshot(page, f"step_{step_num}")
                        _safe_attach_screenshot(ss_path, f"Screenshot - Step {step_num}")

                    # 3. Generate TCs
                    with allure.step("Generate test cases"):
                        try:
                            generate_test_cases(
                                page_text, current_url,
                                buttons=buttons, inputs=inputs, links=links,
                                page_title=page_title,
                            )
                        except Exception as e:
                            print(f"[WARN] TC generation failed: {e}")

                    # 4. Bug Detection
                    with allure.step("Bug detection"):
                        try:
                            page_signals = collect_page_signals(page)
                            page_signals["console_errors"]  = list(console_errors)
                            page_signals["failed_requests"] = list(failed_requests)
                            bug = detect_bug(page_text, page_signals)
                        except Exception as e:
                            print(f"[WARN] Bug detection failed: {e}")
                            bug = {"found": False}

                        if bug.get("found"):
                            with allure.step(f"Bug [{bug['severity']}]: {bug['title']}"):
                                bug_ss = capture_bug_screenshot(
                                    page, label=f"bug_step{step_num}")
                                bug_data = {
                                    "title":       bug["title"],
                                    "description": bug["description"],
                                    "severity":    bug["severity"],
                                    "steps":       [],
                                    "screenshot":  bug_ss,
                                    "additional_info": {
                                        "category":        bug.get("category"),
                                        "url":             current_url,
                                        "page_title":      page_title,
                                        "console_errors":  console_errors[:5],
                                        "failed_requests": failed_requests[:5],
                                    }
                                }
                                bug_report = generate_bug_report(
                                    bug_data, page_text, allure_attach=True)
                                save_bug_report(bug_report)
                                _safe_attach_screenshot(
                                    bug_ss, f"Bug Screenshot - Step {step_num}")

                    # 5. AI Decision
                    with allure.step("AI decision"):
                        try:
                            decision = decide_next_action(
                                page_text, buttons, links, inputs,
                                memory.history(),
                                page_title=page_title,
                                current_url=current_url,
                            )
                        except Exception as e:
                            print(f"[WARN] AI decision failed: {e}")
                            decision = "stop"
                        allure.attach(decision, name="AI Decision",
                                      attachment_type=allure.attachment_type.TEXT)

                    # 6. Execute action
                    with allure.step(f"Execute: {decision}"):
                        try:
                            action_result = execute_action(page, decision)
                        except Exception as e:
                            print(f"[WARN] Action execution failed: {e}")
                            action_result = f"error: {e}"
                        memory.add_action(f"Step {step_num}: {action_result}")
                        tracker.add(action_result, page.url)
                        allure.attach(action_result, name="Action Result",
                                      attachment_type=allure.attachment_type.TEXT)

                    console_errors.clear()
                    failed_requests.clear()

                    if "stop" in action_result.lower() or decision == "stop":
                        with allure.step("Agent chose to stop"):
                            pass
                        break

            tracker.attach_report()
            log_test(agent_id, start_url, "Exploratory Testing", "PASS")

        except Exception as e:
            with allure.step(f"Exception: {e}"):
                try:
                    err_ss = capture_bug_screenshot(page, label="exception")
                except Exception:
                    err_ss = None
                try:
                    bug_report = generate_bug_report(str(e), "", allure_attach=True)
                    bug_report["screenshot"] = err_ss
                    save_bug_report(bug_report)
                except Exception:
                    pass
                # Only attach screenshot if it actually exists
                _safe_attach_screenshot(err_ss, "Exception Screenshot")
            log_test(agent_id, start_url, "Exploratory Testing", "FAIL")
            raise

        finally:
            with allure.step("Close browser"):
                try:
                    page.close()
                    context.close()
                    browser.close()
                except Exception:
                    pass
