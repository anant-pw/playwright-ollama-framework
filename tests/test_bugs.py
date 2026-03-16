# tests/test_bugs.py
#
# FIX: Now reads ONLY bugs from this run's subfolder (bug_reports/RUN_ID/)
# so each Allure build shows only that run's bugs — not every bug ever found.

import pytest
import allure
import glob
import json
import os
from run_context import RUN_ID, BUG_RUN_DIR

_SEVERITY_MAP = {
    "critical": allure.severity_level.CRITICAL,
    "high":     allure.severity_level.CRITICAL,
    "medium":   allure.severity_level.NORMAL,
    "low":      allure.severity_level.MINOR,
}


def _load_bugs() -> list:
    """Load bugs from this run's folder only."""
    if not os.path.isdir(BUG_RUN_DIR):
        print(f"[BUG] No bug folder for run {RUN_ID}: {BUG_RUN_DIR}")
        return []

    # New format: bug_001.json, bug_002.json
    files = sorted(glob.glob(os.path.join(BUG_RUN_DIR, "bug_*.json")))

    bugs = []
    for f in files:
        try:
            data = json.load(open(f, encoding="utf-8"))
            data["_source_file"] = f
            bugs.append(data)
        except Exception as e:
            print(f"[BUG] Could not read {f}: {e}")

    print(f"[BUG] Loaded {len(bugs)} bug(s) from run {RUN_ID}")
    return bugs


def pytest_generate_tests(metafunc):
    if "bug_row" in metafunc.fixturenames:
        bugs = _load_bugs()
        if bugs:
            metafunc.parametrize(
                "bug_row",
                bugs,
                ids=[
                    os.path.splitext(os.path.basename(b["_source_file"]))[0]
                    for b in bugs
                ],
            )
        else:
            metafunc.parametrize("bug_row", [None], ids=["no_bugs_this_run"])


@allure.feature("Bug Reports")
@allure.story(f"Run: {RUN_ID}")
def test_bug(bug_row):
    """
    One FAILED Allure test per detected bug, scoped to this run only.
    Bugs show as red FAILED tests with severity badge in the report.
    """
    if bug_row is None:
        pytest.skip(f"No bugs detected in run {RUN_ID}.")

    title       = bug_row.get("title",       "Unnamed Bug")
    description = bug_row.get("description", "")
    severity    = bug_row.get("severity",    "Medium").lower()
    timestamp   = bug_row.get("timestamp",   "")
    screenshot  = bug_row.get("screenshot",  None)
    steps       = bug_row.get("steps_to_reproduce", [])
    extra       = bug_row.get("additional_info", {})
    run_id      = bug_row.get("run_id", RUN_ID)

    allure.dynamic.title(f"BUG: {title}")
    allure.dynamic.severity(_SEVERITY_MAP.get(severity, allure.severity_level.NORMAL))
    allure.dynamic.description(
        f"**Run ID:** {run_id}\n\n"
        f"**Detected:** {timestamp}\n\n"
        f"**Description:**\n{description}"
    )
    allure.dynamic.tag(f"run:{run_id}")
    allure.dynamic.tag(f"severity:{severity}")
    if extra.get("category"):
        allure.dynamic.tag(f"category:{extra['category']}")

    # Attach full report JSON
    allure.attach(
        json.dumps({k: v for k, v in bug_row.items() if k != "_source_file"},
                   indent=2, default=str),
        name="Full Bug Report",
        attachment_type=allure.attachment_type.JSON,
    )

    # Attach screenshot
    if screenshot:
        abs_ss = os.path.abspath(screenshot)
        if os.path.exists(abs_ss):
            with open(abs_ss, "rb") as f:
                allure.attach(f.read(), name="Bug Screenshot",
                              attachment_type=allure.attachment_type.PNG)
        else:
            print(f"[BUG] Screenshot not found: {abs_ss}")

    with allure.step("Bug details"):
        with allure.step(f"Description: {description[:120]}"):
            allure.attach(description, name="Full Description",
                          attachment_type=allure.attachment_type.TEXT)

        if steps:
            for i, step in enumerate(steps, 1):
                with allure.step(f"Step {i}: {step}"):
                    pass

        if extra:
            allure.attach(
                json.dumps(extra, indent=2, default=str),
                name="Additional Info",
                attachment_type=allure.attachment_type.JSON,
            )

        # Attach console errors and failed requests if present
        console_errs = extra.get("console_errors", [])
        failed_reqs  = extra.get("failed_requests", [])
        if console_errs:
            allure.attach(
                "\n".join(console_errs),
                name="Console Errors",
                attachment_type=allure.attachment_type.TEXT,
            )
        if failed_reqs:
            allure.attach(
                "\n".join(failed_reqs),
                name="Failed Network Requests",
                attachment_type=allure.attachment_type.TEXT,
            )

    # Bugs = FAILED tests in Allure (shows red with severity badge)
    pytest.fail(f"[{severity.upper()}] {title}\n\n{description}")
