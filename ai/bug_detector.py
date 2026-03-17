# ai/bug_detector.py
#
# PHASE 1 UPGRADE: Visual Analysis + Better Detection
# ─────────────────────────────────────────────────────
# NEW: detect_bug_visual() sends actual screenshots to llava vision model
#      so bugs like layout breaks, overlapping elements, wrong colors are caught
#      that text-only analysis would completely miss.
#
# IMPROVED: detect_bug() now tries visual first, falls back to text if no llava.
# IMPROVED: Much stricter dedup — won't re-report same bug type on same URL.

import allure
import json
import base64
import hashlib
import os
import requests
from ai.ollama_client import generate, OllamaUnavailableError, OLLAMA_HOST
from config import CFG

# Track reported bugs to avoid duplicates within a run
_reported_hashes: set = set()

_CATEGORIES = [
    "broken_layout",
    "missing_content",
    "broken_form",
    "navigation_error",
    "console_error",
    "auth_issue",
    "performance",
    "visual_issue",   # NEW — for llava-detected visual bugs
]

# ── Visual model support ──────────────────────────────────────────────────────

def _has_vision_model() -> bool:
    """Check if llava or any vision model is available in Ollama."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        models = [m.get("name", "") for m in r.json().get("models", [])]
        vision_models = [m for m in models if any(
            v in m.lower() for v in ["llava", "bakllava", "vision", "moondream"]
        )]
        if vision_models:
            print(f"[VISUAL] Vision model available: {vision_models[0]}")
            return True
    except Exception:
        pass
    return False


def _get_vision_model() -> str:
    """Get the best available vision model name."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        models = [m.get("name", "") for m in r.json().get("models", [])]
        for m in models:
            if any(v in m.lower() for v in ["llava", "bakllava", "vision", "moondream"]):
                return m
    except Exception:
        pass
    return "llava"


def detect_bug_visual(screenshot_path: str, page_url: str = "",
                      page_title: str = "") -> dict:
    """
    Send screenshot to llava vision model for visual bug detection.
    Catches bugs that text analysis misses:
    - Layout breaks, overlapping elements
    - Images not loading (broken img tags)
    - Wrong colors, contrast issues
    - Cut-off text or buttons
    - Misaligned UI components
    """
    if not screenshot_path or not os.path.exists(screenshot_path):
        return _no_bug()

    vision_model = _get_vision_model()

    try:
        # Read and encode screenshot as base64
        with open(screenshot_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        prompt = f"""You are a senior QA engineer reviewing a screenshot of a web page.
URL: {page_url}
Page title: {page_title}

Look at this screenshot carefully and identify any REAL visual bugs:

LOOK FOR:
- Broken layouts (elements overlapping, cut off, outside their containers)
- Images that failed to load (broken image icons, empty spaces where images should be)
- Text that is cut off, truncated, or overflowing its container
- Buttons or links that appear non-functional or visually broken
- Loading spinners that are stuck or infinite
- Empty sections where content should be
- Severely misaligned elements
- Error messages or HTTP error pages visible

DO NOT REPORT:
- Normal UI design choices (even if you dislike them)
- Minor spacing differences
- Intentional placeholders
- Things that look normal and functional

Respond in EXACT JSON format:
{{
  "found": true or false,
  "severity": "Critical" or "High" or "Medium" or "Low",
  "category": "visual_issue" or "broken_layout" or "missing_content" or "broken_form",
  "title": "short visual bug title (max 10 words)",
  "description": "what visual problem was found and where (2-3 sentences)"
}}

If no visual bug found:
{{"found": false, "severity": "None", "category": "none", "title": "No visual bug", "description": ""}}
"""

        # Call Ollama with image
        payload = {
            "model":  vision_model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
        }

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=(CFG.ollama_connect_timeout, CFG.ollama_read_timeout),
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()

        print(f"[VISUAL] llava response ({len(raw)} chars)")

        try:
            allure.attach(f"Visual analysis via {vision_model}\n\n{raw}",
                          name="Visual Bug Detection",
                          attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass

        # Parse JSON
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1].lstrip("json").strip()

        result = json.loads(clean)
        result["raw"]    = raw
        result["source"] = "visual"
        return result

    except json.JSONDecodeError:
        print(f"[VISUAL] Could not parse llava response as JSON")
        return _no_bug()
    except Exception as e:
        print(f"[VISUAL] Visual detection error: {e}")
        return _no_bug()


def collect_page_signals(page) -> dict:
    """Collect real technical signals from the browser."""
    signals = {
        "console_errors":  [],
        "failed_requests": [],
        "js_errors":       [],
        "page_title":      "",
        "current_url":     "",
    }
    try:
        signals["page_title"]  = page.title()
        signals["current_url"] = page.url

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


def detect_bug(page_text: str, page_signals: dict = None,
               screenshot_path: str = None) -> dict:
    """
    Unified bug detection:
    1. Try visual analysis (llava) if screenshot available
    2. Fall back to text + signal analysis (llama3)
    3. Final fallback: pure signal-based detection

    Returns structured dict with found/severity/category/title/description.
    """
    signals         = page_signals or {}
    console_errors  = signals.get("console_errors", [])
    failed_requests = signals.get("failed_requests", [])
    js_errors       = signals.get("js_errors", [])
    current_url     = signals.get("current_url", "unknown")

    # Dedup check
    sig = hashlib.md5(
        f"{current_url}:{sorted(console_errors)}:{sorted(js_errors)}".encode()
    ).hexdigest()[:8]

    if sig in _reported_hashes:
        return {"found": False, "severity": "None", "category": "duplicate",
                "title": "Duplicate", "description": "", "raw": "DUPLICATE"}
    _reported_hashes.add(sig)

    # ── 1. Visual analysis via llava ─────────────────────────────────────────
    if screenshot_path and _has_vision_model():
        page_title = signals.get("page_title", "")
        visual_result = detect_bug_visual(screenshot_path, current_url, page_title)
        if visual_result.get("found"):
            print(f"[VISUAL] Bug found visually: {visual_result.get('title')}")
            try:
                allure.attach(
                    json.dumps(visual_result, indent=2),
                    name="Visual Bug Found",
                    attachment_type=allure.attachment_type.JSON,
                )
            except Exception:
                pass
            return visual_result

    # ── 2. Text + signal analysis via llama3 ─────────────────────────────────
    prompt = f"""You are a senior QA engineer doing exploratory testing on a web application.

URL: {current_url}

TECHNICAL SIGNALS (most reliable — check these first):
Console errors: {console_errors if console_errors else 'none detected'}
Failed network requests: {failed_requests if failed_requests else 'none detected'}
Visible error messages in DOM: {js_errors if js_errors else 'none detected'}

PAGE CONTENT (first 2000 chars):
{page_text[:2000]}

TASK: Identify REAL bugs. Do NOT report:
- Normal UI text containing words like "error" or "invalid"
- Expected validation messages
- Marketing copy or placeholder text
- Working as designed

DO report:
- JavaScript exceptions or stack traces
- HTTP 4xx/5xx errors
- Broken or missing elements
- Forms that cannot be submitted
- Authentication failures
- Content that failed to load

Respond in EXACT JSON:
{{
  "found": true or false,
  "severity": "Critical" or "High" or "Medium" or "Low",
  "category": one of {_CATEGORIES},
  "title": "short bug title (max 10 words)",
  "description": "what is broken and how to reproduce (2-3 sentences)"
}}

If no bug: {{"found": false, "severity": "None", "category": "none", "title": "No bug", "description": ""}}
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

        clean = raw_result.strip()
        if "```" in clean:
            clean = clean.split("```")[1].lstrip("json").strip()

        result = json.loads(clean)
        result["raw"]    = raw_result
        result["source"] = "text"

    except (json.JSONDecodeError, OllamaUnavailableError):
        result = _signal_fallback(console_errors, failed_requests, js_errors, raw_result)

    try:
        summary = f"Found: {result['found']} | {result['severity']} | {result['title']}"
        allure.attach(summary, name="Bug Detection Result",
                      attachment_type=allure.attachment_type.TEXT)
        if result["found"]:
            allure.attach(json.dumps(result, indent=2),
                          name="Bug Details",
                          attachment_type=allure.attachment_type.JSON)
    except Exception:
        pass

    return result


def _no_bug() -> dict:
    return {"found": False, "severity": "None", "category": "none",
            "title": "No bug", "description": "", "raw": "NO BUG", "source": "none"}


def _signal_fallback(console_errors, failed_requests, js_errors, raw) -> dict:
    """Pure signal-based detection when AI is unavailable."""
    if console_errors:
        return {"found": True, "severity": "High", "category": "console_error",
                "title": "Console errors detected",
                "description": f"Console errors: {console_errors[:3]}",
                "raw": raw, "source": "signals"}
    if failed_requests:
        return {"found": True, "severity": "High", "category": "navigation_error",
                "title": "Network requests failed",
                "description": f"Failed requests: {failed_requests[:3]}",
                "raw": raw, "source": "signals"}
    if js_errors:
        return {"found": True, "severity": "Medium", "category": "console_error",
                "title": "Visible error messages",
                "description": f"Error elements found: {js_errors[:3]}",
                "raw": raw, "source": "signals"}
    return _no_bug()
