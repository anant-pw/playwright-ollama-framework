# tests/test_generated_tcs.py
#
# FIX: Now reads ONLY the current run's TC file from run_context.TC_RUN_FILE
# so each Allure build shows only that run's generated test cases — not a
# growing mix of every previous run.

import pytest
import allure
import os
import json
from run_context import RUN_ID, TC_RUN_FILE


def _load_tcs() -> list:
    """Load TCs from this run's Excel file only."""
    if not os.path.exists(TC_RUN_FILE):
        print(f"[TC] No TC file for run {RUN_ID} yet: {TC_RUN_FILE}")
        return []
    try:
        import pandas as pd
        df = pd.read_excel(TC_RUN_FILE)
        df = df.drop_duplicates(subset="TestID", keep="last")
        print(f"[TC] Loaded {len(df)} TCs from run {RUN_ID}")
        return df.to_dict("records")
    except Exception as e:
        print(f"[TC] Could not load {TC_RUN_FILE}: {e}")
        return []


def pytest_generate_tests(metafunc):
    if "tc_row" in metafunc.fixturenames:
        tcs = _load_tcs()
        if tcs:
            metafunc.parametrize(
                "tc_row",
                tcs,
                ids=[str(tc.get("TestID", f"TC_{i}")) for i, tc in enumerate(tcs)],
            )
        else:
            metafunc.parametrize("tc_row", [None], ids=["no_tcs_yet"])


@allure.feature("AI Generated Test Cases")
@allure.story(f"Run: {RUN_ID}")
def test_generated_tc(tc_row):
    """One Allure test per AI-generated TC, scoped to this run only."""
    if tc_row is None:
        pytest.skip(f"No TCs generated in run {RUN_ID} yet — run test_run_ai_agents first.")

    tc_id      = str(tc_row.get("TestID",         "Unknown"))
    title      = str(tc_row.get("Title",           "Untitled TC"))
    steps_text = str(tc_row.get("Steps",           "No steps"))
    expected   = str(tc_row.get("ExpectedResult",  "No expected result"))
    url        = str(tc_row.get("URL",             ""))
    created_at = str(tc_row.get("CreatedAt",       ""))
    run_id     = str(tc_row.get("RunID",           RUN_ID))

    allure.dynamic.title(f"{tc_id}: {title}")
    allure.dynamic.description(
        f"**Run ID:** {run_id}\n\n"
        f"**URL:** {url}\n\n"
        f"**Steps:** {steps_text}\n\n"
        f"**Expected:** {expected}\n\n"
        f"**Generated:** {created_at}"
    )
    allure.dynamic.severity(allure.severity_level.NORMAL)

    # Tag with run ID so you can filter in Allure
    allure.dynamic.tag(f"run:{run_id}")
    allure.dynamic.tag(f"url:{url[:40]}")

    allure.attach(
        json.dumps(dict(tc_row), indent=2, default=str),
        name=f"TC Details – {tc_id}",
        attachment_type=allure.attachment_type.JSON,
    )

    with allure.step(f"Test case: {title}"):
        with allure.step(f"URL: {url}"):
            allure.attach(url, name="Target URL",
                          attachment_type=allure.attachment_type.TEXT)
        with allure.step(f"Steps: {steps_text}"):
            allure.attach(steps_text, name="Steps",
                          attachment_type=allure.attachment_type.TEXT)
        with allure.step(f"Expected: {expected}"):
            allure.attach(expected, name="Expected Result",
                          attachment_type=allure.attachment_type.TEXT)

    assert title,      "TC must have a title"
    assert steps_text, "TC must have steps"
    assert expected,   "TC must have an expected result"
