# reporting/testcase_writer.py
#
# CHANGE: Each run gets its own Excel file in generated_test_cases/RUN_ID/
# No more appending to a shared file — every run is isolated and traceable.

import pandas as pd
import os
import allure
import json
import base64
from datetime import datetime
from run_context import RUN_ID, TC_RUN_FILE, TC_RUN_DIR


def _parse_tc_lines(ai_output: str, url: str) -> list:
    rows, base_ts = [], int(datetime.now().timestamp())
    for i, line in enumerate(ai_output.split("\n")):
        line = line.strip()
        if not line or line.startswith(("-", "=", "#")):
            continue
        if line.lower().startswith("title") and "steps" in line.lower():
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or not parts[0] or len(parts[0]) < 3:
            continue
        rows.append({
            "RunID":          RUN_ID,
            "TestID":         f"TC_{base_ts}_{i:03d}",
            "Title":          parts[0],
            "Steps":          parts[1],
            "ExpectedResult": parts[2],
            "URL":            url,
            "CreatedBy":      "AI-Agent",
            "CreatedAt":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Status":         "Generated",
        })
    return rows


def save_test_cases(ai_output: str, url: str) -> list:
    rows = _parse_tc_lines(ai_output, url)

    if not rows:
        allure.attach(
            f"No TCs parsed:\n\n{ai_output}",
            name="⚠ TC Parse Failed",
            attachment_type=allure.attachment_type.TEXT,
        )
        return []

    # ── Save to this run's Excel file (never appends to a previous run) ───────
    tc_file = TC_RUN_FILE
    df_new  = pd.DataFrame(rows)

    if os.path.exists(tc_file):
        # Within the SAME run, multiple steps DO append to the same run file
        df_all = pd.concat([pd.read_excel(tc_file), df_new], ignore_index=True)
    else:
        df_all = df_new

    df_all.to_excel(tc_file, index=False)
    print(f"[TC] {len(rows)} TC(s) → {tc_file}  (run {RUN_ID})")

    # ── CSV inline table ───────────────────────────────────────────────────────
    csv_lines = ["TestID,Title,Steps,ExpectedResult,URL"]
    for tc in rows:
        def esc(v): return f'"{v}"' if "," in str(v) else str(v)
        csv_lines.append(
            f"{esc(tc['TestID'])},{esc(tc['Title'])},{esc(tc['Steps'])},"
            f"{esc(tc['ExpectedResult'])},{esc(tc['URL'])}"
        )
    allure.attach(
        "\n".join(csv_lines),
        name=f"📋 Test Cases – {len(rows)} TCs (run {RUN_ID})",
        attachment_type=allure.attachment_type.CSV,
    )

    # ── Excel download link embedded in HTML ──────────────────────────────────
    if os.path.exists(tc_file):
        with open(tc_file, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        download_html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;padding:20px">
<h3 style="margin:0 0 8px">Run: {RUN_ID}</h3>
<p style="color:#555;margin-bottom:16px">{len(df_all)} test case(s) in this run · File: {tc_file}</p>
<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}"
   download="test_cases_{RUN_ID}.xlsx"
   style="display:inline-block;padding:10px 20px;background:#0052cc;color:white;
          border-radius:6px;text-decoration:none;font-weight:600">
  ⬇ Download test_cases_{RUN_ID}.xlsx
</a>
</body></html>"""
        allure.attach(
            download_html,
            name=f"📥 test_cases_{RUN_ID}.xlsx (download)",
            attachment_type=allure.attachment_type.HTML,
        )

    # ── Individual TC JSON blocks ──────────────────────────────────────────────
    for tc in rows:
        allure.attach(
            json.dumps(tc, indent=2),
            name=f"🧪 {tc['TestID']} – {tc['Title'][:60]}",
            attachment_type=allure.attachment_type.JSON,
        )

    return rows
