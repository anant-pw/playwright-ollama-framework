# reporting/bug_reporter.py
#
# CHANGE: Each run gets its own subfolder: bug_reports/20260316_171950/
# Bugs within a run are numbered sequentially: bug_001.json, bug_002.json
# Easy to find all bugs from a specific run in one place.

import json
import os
import datetime
import allure
from run_context import RUN_ID, BUG_RUN_DIR

# Sequential counter for this run's bug files
_bug_counter = 0


def save_bug_report(bug_data: dict, filename: str = None) -> str:
    global _bug_counter
    _bug_counter += 1

    if not filename:
        filename = f"bug_{_bug_counter:03d}.json"

    path = os.path.join(BUG_RUN_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bug_data, f, indent=4)

    print(f"[BUG] Saved: {path}")
    return path


def generate_bug_report(bug_input, page_text: str = "",
                        allure_attach: bool = True) -> dict:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(bug_input, str):
        bug_data = {
            "title":       "AI-Detected Bug",
            "description": bug_input,
            "steps":       [],
            "severity":    "Medium",
            "screenshot":  None,
            "additional_info": {"page_text_snippet": page_text[:500]},
        }
    else:
        bug_data = bug_input

    report = {
        "run_id":             RUN_ID,
        "timestamp":          ts,
        "title":              bug_data.get("title",       "Unnamed Bug"),
        "description":        bug_data.get("description", ""),
        "steps_to_reproduce": bug_data.get("steps",       []),
        "severity":           bug_data.get("severity",    "Medium"),
        "screenshot":         bug_data.get("screenshot",  None),
        "additional_info":    bug_data.get("additional_info", {}),
    }

    if allure_attach:
        try:
            allure.attach(
                json.dumps(report, indent=4),
                name=f"🐛 Bug Report – {report['title']}",
                attachment_type=allure.attachment_type.JSON,
            )
            ss = report.get("screenshot")
            if ss:
                abs_ss = os.path.abspath(ss)
                if os.path.exists(abs_ss):
                    with open(abs_ss, "rb") as f:
                        allure.attach(f.read(), name="Bug Screenshot",
                                      attachment_type=allure.attachment_type.PNG)
        except Exception as e:
            print(f"[WARN] Allure attach failed: {e}")

    return report
