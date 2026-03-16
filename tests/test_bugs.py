# tests/test_bugs.py
#
# FIX: Load bugs at EXECUTION time not collection time.
# Uses a session-scoped marker file written by run_agents.py to find
# the current run's bug folder reliably.

import pytest
import allure
import glob
import json
import os

_SEVERITY_MAP = {
    "critical": allure.severity_level.CRITICAL,
    "high":     allure.severity_level.CRITICAL,
    "medium":   allure.severity_level.NORMAL,
    "low":      allure.severity_level.MINOR,
}


def _get_current_run_id() -> str:
    """Get RUN_ID from run_context — same module so same timestamp."""
    try:
        from run_context import RUN_ID
        return RUN_ID
    except Exception:
        return None


def _load_bugs_for_run(run_id: str) -> list:
    """Load bugs from a specific run folder."""
    from config import CFG
    bug_dir = os.path.join(CFG.bug_reports_dir, run_id)

    if not os.path.isdir(bug_dir):
        return []

    files = sorted(glob.glob(os.path.join(bug_dir, "bug_*.json")))
    bugs  = []
    for f in files:
        try:
            data = json.load(open(f, encoding="utf-8"))
            data["_source_file"] = f
            bugs.append(data)
        except Exception as e:
            print(f"[BUG] Could not read {f}: {e}")

    print(f"[BUG] Loaded {len(bugs)} bug(s) from run {run_id}")
    return bugs


def _load_most_recent_bugs() -> tuple:
    """Fallback: find most recent run folder with bugs."""
    from config import CFG
    bug_base = CFG.bug_reports_dir

    if not os.path.isdir(bug_base):
        return None, []

    subfolders = sorted([
        d for d in os.listdir(bug_base)
        if os.path.isdir(os.path.join(bug_base, d))
    ], reverse=True)

    for folder in subfolders:
        bugs = _load_bugs_for_run(folder)
        if bugs:
            return folder, bugs

    return None, []


def pytest_generate_tests(metafunc):
    if "bug_row" in metafunc.fixturenames:
        # At collection time just create a single placeholder
        # Actual bugs are loaded at execution time via the fixture
        metafunc.parametrize("bug_row", ["__load_at_runtime__"],
                             ids=["bugs"])


@allure.feature("Bug Reports")
def test_bug(bug_row):
    """
    Dynamically loads bugs at execution time — after run_agents.py has run.
    Shows one FAILED Allure entry per bug found.
    """
    # Load bugs NOW (at execution time, not collection time)
    run_id = _get_current_run_id()
    bugs   = _load_bugs_for_run(run_id) if run_id else []

    # If current run has no bugs yet, try most recent run
    if not bugs:
        run_id, bugs = _load_most_recent_bugs()

    if not bugs:
        pytest.skip("No bugs detected in this run.")

    # Report each bug as a separate allure step + fail at end
    bug_titles = []
    for bug in bugs:
        _report_bug_to_allure(bug)
        severity = bug.get("severity", "Medium").lower()
        title    = bug.get("title", "Unnamed Bug")
        bug_titles.append(f"[{severity.upper()}] {title}")

    # Fail the test so bugs show as RED in Allure
    pytest.fail(
        f"{len(bugs)} bug(s) detected in run {run_id}:\n\n" +
        "\n".join(f"  • {t}" for t in bug_titles)
    )


def _report_bug_to_allure(bug_row: dict):
    """Attach a single bug's details to the current Allure test."""
    run_id      = bug_row.get("run_id",      "unknown")
    title       = bug_row.get("title",       "Unnamed Bug")
    description = bug_row.get("description", "")
    severity    = bug_row.get("severity",    "Medium").lower()
    timestamp   = bug_row.get("timestamp",   "")
    screenshot  = bug_row.get("screenshot",  None)
    steps       = bug_row.get("steps_to_reproduce", [])
    extra       = bug_row.get("additional_info", {})

    allure.dynamic.story(f"Run: {run_id}")
    allure.dynamic.severity(_SEVERITY_MAP.get(severity, allure.severity_level.NORMAL))

    with allure.step(f"BUG [{severity.upper()}]: {title}"):
        allure.attach(
            json.dumps({k: v for k, v in bug_row.items()
                        if k != "_source_file"}, indent=2, default=str),
            name=f"Bug Report - {title[:50]}",
            attachment_type=allure.attachment_type.JSON,
        )

        allure.attach(
            f"Run ID: {run_id}\nDetected: {timestamp}\n\n{description}",
            name="Description",
            attachment_type=allure.attachment_type.TEXT,
        )

        if screenshot:
            abs_ss = os.path.abspath(screenshot)
            if os.path.exists(abs_ss):
                with open(abs_ss, "rb") as f:
                    allure.attach(f.read(), name=f"Screenshot - {title[:40]}",
                                  attachment_type=allure.attachment_type.PNG)

        if extra:
            allure.attach(
                json.dumps(extra, indent=2, default=str),
                name="Additional Info",
                attachment_type=allure.attachment_type.JSON,
            )

        console_errs = extra.get("console_errors", [])
        failed_reqs  = extra.get("failed_requests", [])
        if console_errs:
            allure.attach("\n".join(console_errs), name="Console Errors",
                          attachment_type=allure.attachment_type.TEXT)
        if failed_reqs:
            allure.attach("\n".join(failed_reqs), name="Failed Network Requests",
                          attachment_type=allure.attachment_type.TEXT)

        if steps:
            for i, step in enumerate(steps, 1):
                with allure.step(f"Step {i}: {step}"):
                    pass
