# run_context.py
#
# Single source of truth for the current run's timestamp and paths.
# Imported by testcase_writer, bug_reporter, and screenshot — so every
# artifact from one run lands in the same timestamped location.
#
# RUN_ID is set ONCE when this module is first imported (at session start).
# All subsequent imports get the same value — no drift between files.

import os
import datetime
from config import CFG

# e.g. "20260316_171950"
RUN_ID = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Per-run directories ───────────────────────────────────────────────────────
# bug_reports/20260316_171950/
BUG_RUN_DIR = os.path.join(CFG.bug_reports_dir, RUN_ID)

# screenshots/20260316_171950/
SCREENSHOT_RUN_DIR = os.path.join(CFG.screenshots_dir, RUN_ID)

# generated_test_cases/20260316_171950/test_cases.xlsx
TC_RUN_DIR  = os.path.join("generated_test_cases", RUN_ID)
TC_RUN_FILE = os.path.join(TC_RUN_DIR, "test_cases.xlsx")

# Create directories immediately
os.makedirs(BUG_RUN_DIR,       exist_ok=True)
os.makedirs(SCREENSHOT_RUN_DIR, exist_ok=True)
os.makedirs(TC_RUN_DIR,        exist_ok=True)

print(f"[RUN] ID: {RUN_ID}")
print(f"[RUN] TCs       → {TC_RUN_FILE}")
print(f"[RUN] Bugs      → {BUG_RUN_DIR}/")
print(f"[RUN] Screenshots → {SCREENSHOT_RUN_DIR}/")
