# browser/login_handler.py
#
# PHASE 1 NEW: Smart Login with Credentials
# ──────────────────────────────────────────
# Detects login forms automatically and fills them using credentials
# from config.env. Supports:
#   - Standard email/password forms
#   - Username/password forms
#   - Multi-step login (email first, then password on next screen)
#   - SSO/OAuth detection (skips gracefully)
#   - Post-login verification (confirms we got past the login wall)

import allure
import time
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from config import CFG


# ── Login detection helpers ───────────────────────────────────────────────────

_EMAIL_SELECTORS = [
    "input[type='email']",
    "input[name*='email']",
    "input[id*='email']",
    "input[placeholder*='email' i]",
    "input[autocomplete='email']",
    "input[autocomplete='username']",
    "input[name*='user']",
    "input[id*='user']",
    "input[placeholder*='username' i]",
]

_PASSWORD_SELECTORS = [
    "input[type='password']",
    "input[name*='password']",
    "input[id*='password']",
    "input[placeholder*='password' i]",
    "input[autocomplete='current-password']",
]

_SUBMIT_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Sign In')",
    "button:has-text('Log In')",
    "button:has-text('Login')",
    "button:has-text('Sign in')",
    "button:has-text('Continue')",
    "button:has-text('Next')",
    "[data-testid*='login']",
    "[data-testid*='signin']",
    "[data-testid*='submit']",
]

_SSO_INDICATORS = [
    "google", "github", "facebook", "microsoft", "apple",
    "saml", "oauth", "sso", "okta", "auth0"
]


def is_login_page(page: Page) -> bool:
    """Detect if the current page is a login/sign-in page."""
    url_lower   = page.url.lower()
    title_lower = ""
    try:
        title_lower = page.title().lower()
    except Exception:
        pass

    # URL-based detection
    url_keywords = ["login", "signin", "sign-in", "sign_in", "auth",
                    "authenticate", "logon", "log-in"]
    if any(k in url_lower for k in url_keywords):
        return True

    # Title-based detection
    title_keywords = ["sign in", "log in", "login", "signin"]
    if any(k in title_lower for k in title_keywords):
        return True

    # DOM-based detection — password field present = login form
    try:
        for sel in _PASSWORD_SELECTORS:
            if page.locator(sel).count() > 0:
                return True
    except Exception:
        pass

    return False


def detect_login_form(page: Page) -> dict:
    """
    Find all login form elements on the page.
    Returns dict with found selectors.
    """
    result = {
        "email_selector":    None,
        "password_selector": None,
        "submit_selector":   None,
        "is_sso":            False,
        "is_multistep":      False,
    }

    # Check for SSO-only pages (no password field)
    try:
        body_text = page.inner_text("body").lower()
        if any(s in body_text for s in _SSO_INDICATORS):
            # Check if there's also a standard form
            has_password = any(
                page.locator(s).count() > 0 for s in _PASSWORD_SELECTORS
            )
            if not has_password:
                result["is_sso"] = True
                return result
    except Exception:
        pass

    # Find email/username field
    for sel in _EMAIL_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                result["email_selector"] = sel
                break
        except Exception:
            continue

    # Find password field
    for sel in _PASSWORD_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                result["password_selector"] = sel
                break
        except Exception:
            continue

    # Detect multi-step: email present but no password yet
    if result["email_selector"] and not result["password_selector"]:
        result["is_multistep"] = True

    # Find submit button
    for sel in _SUBMIT_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                result["submit_selector"] = sel
                break
        except Exception:
            continue

    return result


def attempt_login(page: Page, email: str, password: str) -> dict:
    """
    Attempt to log in using the provided credentials.
    Returns result dict with success/failure info.
    """
    result = {
        "attempted":    False,
        "success":      False,
        "method":       None,
        "url_before":   page.url,
        "url_after":    None,
        "error":        None,
        "skipped":      False,
        "skip_reason":  None,
    }

    if not email or not password:
        result["skipped"]     = True
        result["skip_reason"] = "No credentials configured"
        return result

    if not is_login_page(page):
        result["skipped"]     = True
        result["skip_reason"] = "Not a login page"
        return result

    form = detect_login_form(page)

    # SSO only — can't automate
    if form["is_sso"]:
        result["skipped"]     = True
        result["skip_reason"] = "SSO-only login detected — skipping"
        print("[LOGIN] SSO-only page detected — skipping auto-login")
        return result

    if not form["email_selector"]:
        result["skipped"]     = True
        result["skip_reason"] = "No email/username field found"
        return result

    result["attempted"] = True

    try:
        # ── Step 1: Fill email/username ───────────────────────────────────────
        print(f"[LOGIN] Filling email field: {form['email_selector']}")
        email_locator = page.locator(form["email_selector"]).first
        email_locator.fill(email)
        time.sleep(0.3)

        # ── Multi-step: submit email first, then fill password ────────────────
        if form["is_multistep"] and form["submit_selector"]:
            print("[LOGIN] Multi-step login detected — submitting email first")
            page.locator(form["submit_selector"]).first.click()
            page.wait_for_timeout(2000)
            # Re-detect form after email submission
            form = detect_login_form(page)
            result["method"] = "multistep"

        # ── Step 2: Fill password ─────────────────────────────────────────────
        if form["password_selector"]:
            print(f"[LOGIN] Filling password field: {form['password_selector']}")
            page.locator(form["password_selector"]).first.fill(password)
            time.sleep(0.3)
            result["method"] = result["method"] or "standard"
        else:
            result["error"] = "Password field not found after email step"
            return result

        # ── Step 3: Submit ────────────────────────────────────────────────────
        if form["submit_selector"]:
            print(f"[LOGIN] Clicking submit: {form['submit_selector']}")
            page.locator(form["submit_selector"]).first.click()
        else:
            # Press Enter as fallback
            page.locator(form["password_selector"]).first.press("Enter")

        # ── Step 4: Wait for navigation / result ──────────────────────────────
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(2000)
        result["url_after"] = page.url

        # ── Step 5: Verify login success ──────────────────────────────────────
        result["success"] = _verify_login_success(page, result["url_before"])

        if result["success"]:
            print(f"[LOGIN] Login successful! Now at: {page.url}")
        else:
            print(f"[LOGIN] Login may have failed. URL: {page.url}")

    except Exception as e:
        result["error"] = str(e)
        print(f"[LOGIN] Login attempt failed: {e}")

    return result


def _verify_login_success(page: Page, url_before: str) -> bool:
    """
    Heuristics to detect if login was successful.
    """
    current_url  = page.url
    url_lower    = current_url.lower()

    # URL changed away from login page = likely success
    login_keywords = ["login", "signin", "sign-in", "auth"]
    was_on_login   = any(k in url_before.lower()  for k in login_keywords)
    still_on_login = any(k in url_lower for k in login_keywords)

    if was_on_login and not still_on_login:
        return True

    # Dashboard/home/profile URL = likely success
    success_keywords = ["dashboard", "home", "profile", "account",
                        "welcome", "overview", "app", "main"]
    if any(k in url_lower for k in success_keywords):
        return True

    # Check for error messages still visible
    try:
        error_selectors = [
            "[class*='error']:visible",
            "[role='alert']:visible",
            ".alert-danger:visible",
        ]
        for sel in error_selectors:
            if page.locator(sel).count() > 0:
                return False
    except Exception:
        pass

    # Password field still visible = login form still showing = failed
    try:
        if page.locator("input[type='password']:visible").count() > 0:
            return False
    except Exception:
        pass

    return True


def login_if_needed(page: Page) -> dict:
    """
    Main entry point — call this after navigating to any page.
    Automatically detects and attempts login if credentials are configured.
    """
    email    = getattr(CFG, "login_email",    "")
    password = getattr(CFG, "login_password", "")

    if not email or not password:
        return {"skipped": True, "skip_reason": "No LOGIN_EMAIL/LOGIN_PASSWORD in config"}

    if not is_login_page(page):
        return {"skipped": True, "skip_reason": "Not a login page"}

    with allure.step("Smart Login Attempt"):
        result = attempt_login(page, email, password)

        status = "SKIPPED" if result["skipped"] else ("SUCCESS" if result["success"] else "FAILED")
        print(f"[LOGIN] {status}: {result.get('skip_reason') or result.get('error') or result.get('url_after', '')}")

        try:
            allure.attach(
                json_safe(result),
                name=f"Login Result: {status}",
                attachment_type=allure.attachment_type.JSON,
            )
        except Exception:
            pass

        return result


def json_safe(d: dict) -> str:
    import json
    return json.dumps({k: str(v) for k, v in d.items()}, indent=2)
