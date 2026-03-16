# conftest.py

import pytest
import allure
import subprocess
import os
import platform
from config import CFG


# ── Browser fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_type_launch_args():
    return CFG.browser_launch_kwargs()


@pytest.fixture(scope="session")
def browser_context_args():
    return CFG.browser_context_kwargs()


@pytest.fixture
def page(browser):
    context = browser.new_context(**CFG.browser_context_kwargs())
    pg = context.new_page()
    yield pg
    try:
        allure.attach(pg.url, name="Final URL",
                      attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass
    context.close()


# ── Write environment.properties for Allure ───────────────────────────────────

def pytest_configure(config):
    # Import run_context HERE so RUN_ID is created exactly once at session start
    from run_context import RUN_ID, BUG_RUN_DIR, TC_RUN_FILE, SCREENSHOT_RUN_DIR

    results_dir = CFG.allure_results_dir
    if not os.path.isabs(results_dir):
        results_dir = os.path.join(os.getcwd(), results_dir)
    os.makedirs(results_dir, exist_ok=True)

    try:
        import platform as _p
        lines = [
            f"Run.ID={RUN_ID}",
            f"Target.URLs={', '.join(CFG.target_urls)}",
            f"Browser={CFG.browser}",
            f"Headless={CFG.headless}",
            f"Max.Steps={CFG.max_steps}",
            f"Ollama.Model={CFG.ollama_model}",
            f"TC.File={TC_RUN_FILE}",
            f"Bug.Reports={BUG_RUN_DIR}",
            f"Screenshots={SCREENSHOT_RUN_DIR}",
            f"Python={_p.python_version()}",
            f"OS={_p.system()} {_p.release()}",
        ]
        with open(os.path.join(results_dir, "environment.properties"), "w") as f:
            f.write("\n".join(lines))
    except Exception as e:
        print(f"[ALLURE] environment.properties error: {e}")


# ── Auto-open all reports after session ───────────────────────────────────────

def pytest_sessionfinish(session, exitstatus):
    from run_context import RUN_ID
    print(f"\n{'─'*60}")
    print(f"[RUN] Completed: {RUN_ID}")
    _generate_allure_report()
    _generate_bug_report(RUN_ID)
    _generate_tc_viewer(RUN_ID)
    print("─" * 60)


def _generate_allure_report():
    results_dir = os.path.abspath(CFG.allure_results_dir)
    report_dir  = os.path.abspath(CFG.allure_report_dir)
    if not os.path.exists(results_dir):
        return
    result_files = [f for f in os.listdir(results_dir) if f.endswith(".json")]
    if not result_files:
        print("[ALLURE] No results — skipping.")
        return
    print(f"[ALLURE] {len(result_files)} result(s). Generating report...")
    try:
        gen = subprocess.run(
            ["allure", "generate", results_dir, "--clean", "-o", report_dir],
            capture_output=True, text=True, timeout=60,
        )
        if gen.returncode == 0:
            index = os.path.join(report_dir, "index.html")
            print(f"[ALLURE] → {index}")
            _open(index)
            return
        print(f"[ALLURE] generate failed: {gen.stderr.strip()}")
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        print("[ALLURE] generate timed out.")
    try:
        subprocess.Popen(["allure", "serve", results_dir])
    except FileNotFoundError:
        print(f"[ALLURE] Run manually: allure serve {results_dir}")


def _generate_bug_report(run_id: str):
    try:
        import glob
        bug_dir = os.path.join(CFG.bug_reports_dir, run_id)
        if not os.path.isdir(bug_dir) or not glob.glob(os.path.join(bug_dir, "bug_*.json")):
            print(f"[BUG REPORT] No bugs in run {run_id}.")
            return
        from reporting.bug_report_viewer import generate_html_report, open_report
        path = generate_html_report(run_id)
        if path:
            open_report(path)
    except Exception as e:
        print(f"[BUG REPORT] Error: {e}")


def _generate_tc_viewer(run_id: str):
    try:
        from reporting.tc_viewer import generate_html_viewer, open_viewer
        path = generate_html_viewer(run_id)
        if path:
            open_viewer(path)
    except Exception as e:
        print(f"[TC VIEWER] Error: {e}")


def _open(path: str):
    try:
        s = platform.system()
        if s == "Windows": os.startfile(path)
        elif s == "Darwin": subprocess.Popen(["open", path])
        else:               subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Could not open {path}: {e}")
