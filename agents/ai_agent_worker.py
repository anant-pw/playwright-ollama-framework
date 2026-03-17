# agents/ai_agent_worker.py
#
# PHASE 1 UPGRADE: Visual Analysis + Smart Login + Self-Healing
# ──────────────────────────────────────────────────────────────
# 1. VISUAL: Screenshots now passed to detect_bug() for llava visual analysis
# 2. LOGIN:  Automatically detects and fills login forms using config credentials
# 3. HEALING: action_executor.py now has 5-strategy self-healing per action
# 4. ROBUST: All steps wrapped in try/except — agent never crashes on one failure

import allure
from playwright.sync_api import Playwright, TimeoutError as PlaywrightTimeoutError
from config import CFG

from ai.bug_detector import detect_bug, collect_page_signals
from ai.ai_client import ask_ai
from ai.test_generator import generate_test_cases

from browser.dom_extractor import extract_page_info
from browser.screenshot import capture_bug_screenshot, capture_step_screenshot
from browser.login_handler import login_if_needed, is_login_page

from reporting.bug_reporter import save_bug_report, generate_bug_report
from reporting.test_reporter import log_test

from brain.decision_engine import decide_next_action
from brain.action_executor import execute_action
from brain.state_memory import StateMemory
from brain.exploration_tracker import ExplorationTracker


def _safe_goto(page, url: str, timeout: int):
    """Try multiple wait strategies for slow/bot-protected sites."""
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
    """Attach screenshot to Allure only if the file exists."""
    if ss_path and isinstance(ss_path, str):
        try:
            import os
            if os.path.exists(ss_path):
                with open(ss_path, "rb") as f:
                    allure.attach(f.read(), name=name,
                                  attachment_type=allure.attachment_type.PNG)
            else:
                print(f"[WARN] Screenshot missing, skipping: {ss_path}")
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
            # ── Navigate ──────────────────────────────────────────────────────
            with allure.step("Navigate to start URL"):
                loaded = _safe_goto(page, start_url, CFG.page_timeout)
                if not loaded:
                    print(f"[WARN] Page may not have fully loaded, continuing...")
                allure.attach(start_url, name="Start URL",
                              attachment_type=allure.attachment_type.TEXT)
                allure.attach(
                    f"Page loaded: {loaded}\nCurrent URL: {page.url}",
                    name="Navigation Result",
                    attachment_type=allure.attachment_type.TEXT,
                )

            # ── SMART LOGIN: Auto-detect and fill login form ──────────────────
            with allure.step("Smart Login Check"):
                login_result = login_if_needed(page)
                if login_result.get("attempted"):
                    status = "SUCCESS" if login_result["success"] else "FAILED"
                    print(f"[LOGIN] Auto-login {status}")
                    # Take screenshot after login attempt
                    login_ss = capture_step_screenshot(page, "after_login")
                    _safe_attach_screenshot(login_ss, "After Login Attempt")

                    if login_result["success"]:
                        # Clear any login-page signals
                        console_errors.clear()
                        failed_requests.clear()
                elif login_result.get("skipped"):
                    print(f"[LOGIN] Skipped: {login_result.get('skip_reason')}")

            # ── Main exploration loop ─────────────────────────────────────────
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

                    # 2. Screenshot (used for both report + visual bug detection)
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

                    # 4. Bug Detection (UPGRADED: visual + text + signals)
                    with allure.step("Bug detection"):
                        try:
                            page_signals = collect_page_signals(page)
                            page_signals["console_errors"]  = list(console_errors)
                            page_signals["failed_requests"] = list(failed_requests)

                            # Pass screenshot to enable visual detection via llava
                            bug = detect_bug(
                                page_text,
                                page_signals=page_signals,
                                screenshot_path=ss_path,   # NEW: visual analysis
                            )
                        except Exception as e:
                            print(f"[WARN] Bug detection failed: {e}")
                            bug = {"found": False}

                        if bug.get("found"):
                            source = bug.get("source", "text")
                            with allure.step(
                                f"Bug [{bug['severity']}] ({source}): {bug['title']}"
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
                                        "category":        bug.get("category"),
                                        "detection_source": source,
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

                    # 6. Execute action (SELF-HEALING: 5 strategies per action)
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

                    # 7. Check if login appeared mid-session (e.g. session expired)
                    if is_login_page(page):
                        with allure.step("Re-login detected mid-session"):
                            print("[LOGIN] Session expired or redirect to login — re-attempting")
                            re_login = login_if_needed(page)
                            if re_login.get("success"):
                                print("[LOGIN] Re-login successful")
                                console_errors.clear()
                                failed_requests.clear()

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
