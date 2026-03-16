# browser/screenshot.py
#
# CHANGE: Screenshots now go into screenshots/RUN_ID/ subfolder
# so all screenshots from one run are grouped together.

import os
import time
import allure
from playwright.sync_api import Page
from run_context import RUN_ID, SCREENSHOT_RUN_DIR


def capture_bug_screenshot(page: Page, label: str = "bug") -> str:
    filename = f"{label}_{int(time.time() * 1000)}.png"
    path     = os.path.join(SCREENSHOT_RUN_DIR, filename)
    try:
        page.screenshot(path=path, full_page=True)
        print(f"[SCREENSHOT] {path}")
    except Exception as e:
        print(f"[WARN] Screenshot failed: {e}")
    return path


def capture_step_screenshot(page: Page, step_name: str) -> str:
    safe = step_name.replace(" ", "_").replace("/", "-")[:50]
    return capture_bug_screenshot(page, label=safe)
