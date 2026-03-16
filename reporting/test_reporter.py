# reporting/test_reporter.py
"""
Allure-integrated test reporter.
Fix: previously only printed to stdout — nothing appeared in Allure HTML report.
Now attaches every result as JSON so it shows up in the report.
"""

import allure
import datetime
import json


def init_report():
    allure.attach(
        f"Suite started at {datetime.datetime.now().isoformat()}",
        name="Suite Start Time",
        attachment_type=allure.attachment_type.TEXT,
    )
    print("[REPORT] Report initialized")


def close_report():
    allure.attach(
        f"Suite finished at {datetime.datetime.now().isoformat()}",
        name="Suite End Time",
        attachment_type=allure.attachment_type.TEXT,
    )
    print("[REPORT] Report closed")


def log_test(agent_id: str, url: str, test_type: str, status: str):
    """
    KEY FIX: was only print() — now attaches to Allure so it appears in report.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "agent": agent_id,
        "url": url,
        "type": test_type,
        "status": status,
        "timestamp": timestamp,
    }

    allure.attach(
        json.dumps(entry, indent=2),
        name=f"Test Result – {agent_id} [{status}]",
        attachment_type=allure.attachment_type.JSON,
    )
    print(f"[REPORT] {timestamp} | Agent {agent_id} | {url} | {test_type} | {status}")
