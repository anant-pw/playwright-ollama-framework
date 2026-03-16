# reporting/testcase_writer.py
#
# FIX: Handles ALL Ollama output formats including vertical table:
#   Test Case 1: Title
#   | Title | value |
#   | Steps | value |
#   | Expected Result | value |

import pandas as pd
import os
import re
import json
import allure
import base64
from datetime import datetime
from run_context import RUN_ID, TC_RUN_FILE, TC_RUN_DIR


def _parse_tc_lines(ai_output: str, url: str) -> list:
    rows    = []
    base_ts = int(datetime.now().timestamp())

    # ── Try JSON format ───────────────────────────────────────────────────────
    try:
        clean = ai_output.strip()
        if clean.startswith("[") or '"title"' in clean.lower():
            if "```" in clean:
                clean = clean.split("```")[1].lstrip("json").strip()
            data = json.loads(clean)
            if isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        title    = item.get("title", item.get("Title", "")).strip()
                        steps    = item.get("steps", item.get("Steps", "")).strip()
                        expected = item.get("expected", item.get("ExpectedResult",
                                   item.get("expected_result", ""))).strip()
                        if title and steps:
                            rows.append(_make_row(base_ts, i, title, steps, expected, url))
                if rows:
                    return rows
    except Exception:
        pass

    lines = ai_output.strip().split("\n")

    # ── Try vertical table format (Ollama's most common output) ──────────────
    # Test Case 1: Title here          ← or **Test Case 1: Title here**
    # | Title | value |
    # | Steps | do this and that |
    # | Expected Result | this happens |
    vert_rows = []
    current   = {}
    tc_index  = 0

    for line in lines:
        s = line.strip()
        if not s:
            continue

        # Detect heading: "Test Case N: Title" or "**Test Case N: Title**"
        plain_heading = re.match(
            r"^(?:Test Case\s*\d+[:\-]\s*)(.+)$", s, re.IGNORECASE)
        bold_heading  = re.match(
            r"^\*{1,2}(?:Test Case\s*\d+[:\-]?\s*)?(.+?)\*{1,2}$",
            s, re.IGNORECASE)

        if plain_heading or bold_heading:
            # Flush previous TC
            if current.get("title") and current.get("steps"):
                vert_rows.append(_make_row(
                    base_ts, tc_index,
                    current["title"], current["steps"],
                    current.get("expected", ""), url))
                tc_index += 1
            heading_title = (plain_heading or bold_heading).group(1).strip()
            current = {"title": heading_title, "steps": "", "expected": ""}
            continue

        # Vertical table row: | Key | Value |
        if s.startswith("|") and s.endswith("|") and current is not None:
            parts = [p.strip() for p in s.split("|") if p.strip()]
            if len(parts) >= 2:
                key = parts[0].lower()
                val = " ".join(parts[1:]).strip()  # join in case value had |
                if "title" in key:
                    if not current.get("title") or len(val) > 3:
                        current["title"] = val
                elif "step" in key:
                    current["steps"] = val
                elif "expected" in key or "result" in key:
                    current["expected"] = val
                elif "---" in parts[0]:
                    pass  # separator row, skip
            continue

    # Flush last TC
    if current.get("title") and current.get("steps"):
        vert_rows.append(_make_row(
            base_ts, tc_index,
            current["title"], current["steps"],
            current.get("expected", ""), url))

    if vert_rows:
        return vert_rows

    # ── Try horizontal bold-heading + table format ────────────────────────────
    # **Test Case 1: Title**
    # | Steps | Expected Result |
    # | --- | --- |
    # | step text | expected text |
    horiz_rows    = []
    current_title = ""
    all_steps     = []
    all_expected  = []
    tc_index      = 0

    for line in lines:
        s = line.strip()
        bold = re.match(
            r"^\*{1,2}(?:Test Case\s*\d+[:\-]?\s*)?(.+?)\*{1,2}$",
            s, re.IGNORECASE)
        if bold:
            if current_title and all_steps:
                horiz_rows.append(_make_row(
                    base_ts, tc_index, current_title,
                    " | ".join(all_steps),
                    " | ".join(all_expected) if all_expected else "", url))
                tc_index += 1
            current_title = bold.group(1).strip()
            all_steps     = []
            all_expected  = []
            continue

        if re.match(r"(?i)^\|\s*steps?\s*\|", s) or \
           re.match(r"^\|[\s\-|]+\|$", s):
            continue

        if s.startswith("|") and s.endswith("|") and current_title:
            parts = [p.strip() for p in s.split("|") if p.strip()]
            if len(parts) >= 2:
                step_txt = re.sub(r"^\d+\.\s*", "", parts[0]).strip()
                exp_txt  = parts[1].strip()
                if step_txt and step_txt != "---":
                    all_steps.append(step_txt)
                if exp_txt and exp_txt != "---":
                    all_expected.append(exp_txt)

    if current_title and all_steps:
        horiz_rows.append(_make_row(
            base_ts, tc_index, current_title,
            " | ".join(all_steps),
            " | ".join(all_expected) if all_expected else "", url))

    if horiz_rows:
        return horiz_rows

    # ── Try simple pipe-separated: Title | Steps | Expected ──────────────────
    pipe_rows = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith(("-", "=", "#", "*")):
            continue
        if re.match(r"(?i)title\s*\|", s):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) >= 3 and len(parts[0]) >= 5:
            title    = re.sub(r"^\d+[\.\)]\s*", "", parts[0]).strip()
            steps    = parts[1].strip()
            expected = parts[2].strip()
            if title and steps and expected:
                pipe_rows.append(_make_row(base_ts, i, title, steps, expected, url))
    if pipe_rows:
        return pipe_rows

    # ── Try numbered / structured format ──────────────────────────────────────
    current_title = current_steps = current_expected = ""
    tc_index = 0

    for line in lines:
        s = line.strip()
        if not s:
            if current_title and current_steps:
                rows.append(_make_row(base_ts, tc_index,
                                      current_title, current_steps,
                                      current_expected, url))
                tc_index += 1
                current_title = current_steps = current_expected = ""
            continue

        num_match = re.match(
            r"^(?:\d+[\.\):]|TC\d+:?)\s*(.+)", s, re.IGNORECASE)
        if num_match:
            if current_title and current_steps:
                rows.append(_make_row(base_ts, tc_index,
                                      current_title, current_steps,
                                      current_expected, url))
                tc_index += 1
            current_title    = num_match.group(1).strip()
            current_steps    = ""
            current_expected = ""
            continue

        steps_match = re.match(
            r"^(?:steps?|action|how)[:\-]\s*(.+)", s, re.IGNORECASE)
        if steps_match:
            current_steps = steps_match.group(1).strip()
            continue

        expected_match = re.match(
            r"^(?:expected|result|outcome)[:\-]\s*(.+)", s, re.IGNORECASE)
        if expected_match:
            current_expected = expected_match.group(1).strip()
            continue

        if current_title and not current_steps and len(s) > 10:
            current_steps = s
            continue

        if current_title and current_steps and not current_expected and len(s) > 5:
            current_expected = s
            continue

    if current_title and current_steps:
        rows.append(_make_row(base_ts, tc_index,
                              current_title, current_steps,
                              current_expected, url))

    return rows


def _make_row(base_ts: int, index: int, title: str, steps: str,
              expected: str, url: str) -> dict:
    return {
        "RunID":          RUN_ID,
        "TestID":         f"TC_{base_ts}_{index:03d}",
        "Title":          title,
        "Steps":          steps,
        "ExpectedResult": expected or "Test completes without errors",
        "URL":            url,
        "CreatedBy":      "AI-Agent",
        "CreatedAt":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Status":         "Generated",
    }


def save_test_cases(ai_output: str, url: str) -> list:
    rows = _parse_tc_lines(ai_output, url)

    if not rows:
        try:
            allure.attach(
                f"Raw AI output (could not parse TCs):\n\n{ai_output}",
                name="TC Parse Failed - Raw Output",
                attachment_type=allure.attachment_type.TEXT,
            )
        except Exception:
            pass
        print(f"[TC] 0 test case(s) generated for web page")
        return []

    tc_file = TC_RUN_FILE
    df_new  = pd.DataFrame(rows)

    if os.path.exists(tc_file):
        df_all = pd.concat([pd.read_excel(tc_file), df_new], ignore_index=True)
    else:
        df_all = df_new

    df_all.to_excel(tc_file, index=False)
    print(f"[TC] {len(rows)} TC(s) saved -> {tc_file}  (run {RUN_ID})")

    try:
        csv_lines = ["TestID,Title,Steps,ExpectedResult,URL"]
        for tc in rows:
            def esc(v): return f'"{v}"' if "," in str(v) else str(v)
            csv_lines.append(
                f"{esc(tc['TestID'])},{esc(tc['Title'])},{esc(tc['Steps'])},"
                f"{esc(tc['ExpectedResult'])},{esc(tc['URL'])}"
            )
        allure.attach(
            "\n".join(csv_lines),
            name=f"Test Cases - {len(rows)} TCs (run {RUN_ID})",
            attachment_type=allure.attachment_type.CSV,
        )

        if os.path.exists(tc_file):
            with open(tc_file, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            download_html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;padding:20px">
<h3>Run: {RUN_ID}</h3>
<p style="color:#555">{len(df_all)} test case(s) - File: {tc_file}</p>
<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}"
   download="test_cases_{RUN_ID}.xlsx"
   style="display:inline-block;padding:10px 20px;background:#0052cc;color:white;
          border-radius:6px;text-decoration:none;font-weight:600">
  Download test_cases_{RUN_ID}.xlsx
</a>
</body></html>"""
            allure.attach(
                download_html,
                name=f"test_cases_{RUN_ID}.xlsx (download)",
                attachment_type=allure.attachment_type.HTML,
            )

        for tc in rows:
            allure.attach(
                json.dumps(tc, indent=2),
                name=f"{tc['TestID']} - {tc['Title'][:60]}",
                attachment_type=allure.attachment_type.JSON,
            )
    except Exception as e:
        print(f"[WARN] Allure TC attach failed: {e}")

    return rows
