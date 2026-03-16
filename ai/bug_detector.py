# ai/bug_detector.py
#
# IMPROVEMENT: Much more specific bug detection.
# Old prompt just asked "is there a bug?" — got false positives on normal
# words like "error" or "invalid" appearing in UI text.
#
# New approach:
# 1. Captures actual console errors and failed network requests (real signals)
# 2. Structured prompt with specific bug categories to look for
# 3. Returns severity + category, not just a plain string
# 4. Deduplication — same bug on same URL not re-reported

import allure
import json
import hashlib
import os
from ai.ollama_client import generate, OllamaUnavailableError
from config import CFG

# Track reported bugs to avoid duplicates within a run
_reported_hashes: set = set()

_CATEGORIES = [
    "broken_layout",      # elements overlapping, cut off, invisible
    "missing_content",    # expected text/images not present
    "broken_form",        # form fields, validation, submission issues
    "navigation_error",   # broken links, 404s, wrong redirects
    "console_error",      # JS exceptions, network failures
    "auth_issue",         # login, session, permission problems
    "performance",        # page freeze, infinite spinner, timeout
]


def collect_page_signals(page) -> dict:
    """
    Collect real technical signals from the browser:
    console errors, failed requests, JS errors.
    This gives far more reliable bug signals than parsing page text.
    """
    signals = {
        "console_errors": [],
        "failed_requests": [],
        "js_errors": [],
        "page_title": "",
        "current_url": "",
    }
    try:
        signals["page_title"]   = page.title()
        signals["current_url"]  = page.url

        # Check for visible error indicators in the DOM
        error_selectors = [
            "[class*='error']:visible",
            "[class*='Error']:visible",
            "[role='alert']:visible",
            ".alert-danger:visible",
            "[data-testid*='error']:visible",
        ]
        for sel in error_selectors:
            try:
                els = page.locator(sel).all_inner_texts()
                if els:
                    signals["js_errors"].extend(
                        [t.strip() for t in els if t.strip()][:5]
                    )
            except Exception:
                pass

    except Exception as e:
        print(f"[BUG] Signal collection error: {e}")

    return signals


def detect_bug(page_text: str, page_signals: dict = None) -> dict:
    """
    Analyse the page for real bugs.
    Returns a structured dict:
      {
        "found": bool,
        "severity": "Critical|High|Medium|Low|None",
        "category": str,
        "title": str,
        "description": str,
        "raw": str
      }
    """
    signals = page_signals or {}
    console_errors   = signals.get("console_errors", [])
    failed_requests  = signals.get("failed_requests", [])
    js_errors        = signals.get("js_errors", [])
    current_url      = signals.get("current_url", "unknown")

    # Build a dedup hash — same page + same errors = same bug
    sig = hashlib.md5(
        f"{current_url}:{sorted(console_errors)}:{sorted(js_errors)}".encode()
    ).hexdigest()[:8]

    if sig in _reported_hashes:
        return {"found": False, "severity": "None", "category": "duplicate",
                "title": "Duplicate", "description": "", "raw": "DUPLICATE"}
    _reported_hashes.add(sig)

    prompt = f"""You are a senior QA engineer doing exploratory testing on a web application.

URL: {current_url}

TECHNICAL SIGNALS (most reliable — check these first):
Console errors: {console_errors if console_errors else 'none detected'}
Failed network requests: {failed_requests if failed_requests else 'none detected'}
Visible error messages in DOM: {js_errors if js_errors else 'none detected'}

PAGE CONTENT (first 2000 chars):
{page_text[:2000]}

TASK: Identify REAL bugs. Do NOT report:
- Normal UI text that happens to contain words like "error" or "invalid"
- Expected validation messages shown intentionally
- Marketing copy or placeholder text
- Things that are working as designed

DO report:
- JavaScript exceptions or stack traces
- HTTP 4xx/5xx errors
- Elements that are broken, missing, or overlapping unexpectedly
- Forms that cannot be submitted
- Infinite loading spinners
- Authentication/session failures
- Content that failed to load

Respond in this EXACT JSON format (no other text):
{{
  "found": true or false,
  "severity": "Critical" or "High" or "Medium" or "Low",
  "category": one of {_CATEGORIES},
  "title": "short bug title (max 10 words)",
  "description": "what is broken and how to reproduce (2-3 sentences)"
}}

If no real bug found, respond:
{{"found": false, "severity": "None", "category": "none", "title": "No bug", "description": ""}}
"""

    try:
        allure.attach(prompt, name="Bug Detection Prompt",
                      attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass

    raw_result = ""
    try:
        raw_result = generate(prompt)
        if not raw_result:
            return _no_bug()

        # Parse JSON response
        clean = raw_result.strip()
        if "```" in clean:
            clean = clean.split("```")[1].lstrip("json").strip()

        result = json.loads(clean)
        result["raw"] = raw_result

    except (json.JSONDecodeError, OllamaUnavailableError):
        # Fall back to signal-based detection if AI fails
        result = _signal_fallback(console_errors, failed_requests, js_errors, raw_result)

    try:
        summary = f"Found: {result['found']} | {result['severity']} | {result['title']}"
        allure.attach(summary, name="Bug Detection Result",
                      attachment_type=allure.attachment_type.TEXT)
        if result["found"]:
            allure.attach(json.dumps(result, indent=2),
                          name="Bug Details (structured)",
                          attachment_type=allure.attachment_type.JSON)
    except Exception:
        pass

    return result


def _no_bug() -> dict:
    return {"found": False, "severity": "None", "category": "none",
            "title": "No bug", "description": "", "raw": "NO BUG"}


def _signal_fallback(console_errors, failed_requests, js_errors, raw) -> dict:
    """Used when AI is unavailable — rely purely on technical signals."""
    if console_errors:
        return {"found": True, "severity": "High", "category": "console_error",
                "title": "Console errors detected",
                "description": f"Console errors: {console_errors[:3]}",
                "raw": raw}
    if failed_requests:
        return {"found": True, "severity": "High", "category": "navigation_error",
                "title": "Network requests failed",
                "description": f"Failed requests: {failed_requests[:3]}",
                "raw": raw}
    if js_errors:
        return {"found": True, "severity": "Medium", "category": "console_error",
                "title": "Visible error messages",
                "description": f"Error elements found: {js_errors[:3]}",
                "raw": raw}
    return _no_bug()
