# browser/screenshot.py
#
# FIX: Returns None instead of a path if screenshot fails
# so callers can safely check existence before opening

import os
import time
import allure
from playwright.sync_api import Page
from run_context import RUN_ID, SCREENSHOT_RUN_DIR


def capture_bug_screenshot(page: Page, label: str = "bug") -> str | None:
    filename = f"{label}_{int(time.time() * 1000)}.png"
    path     = os.path.join(SCREENSHOT_RUN_DIR, filename)
    try:
        page.screenshot(path=path, full_page=True, timeout=15000)
        print(f"[SCREENSHOT] {path}")
        return path
    except Exception as e:
        print(f"[WARN] Screenshot failed: {e}")
        return None   # Return None so callers can check


def capture_step_screenshot(page: Page, step_name: str) -> str | None:
    safe = step_name.replace(" ", "_").replace("/", "-")[:50]
    return capture_bug_screenshot(page, label=safe)
