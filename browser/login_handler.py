# browser/login_handler.py
#
# PHASE 1 UPGRADE: Smart Login with Credentials
# FIX: Added ID-based selectors — catches sites like myperfectresume.com
#      that use type="text" with custom IDs instead of type="email"

import allure
import time
import json
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from config import CFG

# ── Email/username selectors — ordered from most specific to most generic ─────
_EMAIL_SELECTORS = [
    # Type-based (standard)
    "input[type='email']:visible",
    # ID-based (custom sites like myperfectresume.com)
    "input[id*='email']:visible",
    "input[id*='user']:visible",
    "input[id*='login']:visible",
    "input[id*='username']:visible",
    # Name-based
    "input[name*='email']:visible",
    "input[name*='user']:visible",
    "input[name*='login']:visible",
    # Placeholder-based
    "input[placeholder*='email' i]:visible",
    "input[placeholder*='username' i]:visible",
    # Autocomplete
    "input[autocomplete='email']:visible",
    "input[autocomplete='username']:visible",
    # Type text with email-like context (myperfectresume pattern)
    "input[type='text'][id*='email']:visible",
    "input[type='text'][placeholder*='email' i]:visible",
    "input[type='text'][placeholder*='username' i]:visible",
]

_PASSWORD_SELECTORS = [
    "input[type='password']:visible",
    "input[id*='password']:visible",
    "input[name*='password']:visible",
    "input[placeholder*='password' i]:visible",
    "input[autocomplete='current-password']:visible",
]

_SUBMIT_SELECTORS = [
    # ID-based (most reliable for custom sites)
    "button[id*='signin']:visible",
    "button[id*='SignIn']:visible",
    "button[id*='login']:visible",
    "button[id*='Login']:visible",
    "button[id*='submit']:visible",
    "button[id*='Submit']:visible",
    # Type-based
    "button[type='submit']:visible",
    "input[type='submit']:visible",
    # Text-based
    "button:has-text('Sign In'):visible",
    "button:has-text('Log In'):visible",
    "button:has-text('Login'):visible",
    "button:has-text('Sign in'):visible",
    "button:has-text('SUBMIT'):visible",
    "button:has-text('Submit'):visible",
    "button:has-text('Continue'):visible",
    "button:has-text('Next'):visible",
    # Data attributes
    "[data-testid*='login']:visible",
    "[data-testid*='signin']:visible",
    "[data-testid*='submit']:visible",
]

_SSO_INDICATORS = [
    "google", "github", "facebook", "microsoft", "apple",
    "saml", "oauth", "sso", "okta", "auth0"
]

# ── Cookie consent handling ───────────────────────────────────────────────────

_COOKIE_ACCEPT_SELECTORS = [
    "button:has-text('Accept All'):visible",
    "button:has-text('Accept all'):visible",
    "button:has-text('Accept Cookies'):visible",
    "button:has-text('I Accept'):visible",
    "button:has-text('Got it'):visible",
    "button:has-text('OK'):visible",
    "[id*='accept']:visible",
    "[id*='cookie-accept']:visible",
    ".cookie-accept:visible",
]


def _dismiss_cookie_banner(page: Page):
    """Try to dismiss cookie consent banners before interacting with forms."""
    for sel in _COOKIE_ACCEPT_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.click(timeout=3000)
                print(f"[LOGIN] Dismissed cookie banner: {sel}")
                page.wait_for_timeout(500)
                return True
        except Exception:
            continue
    return False


def is_login_page(page: Page) -> bool:
    """Detect if the current page is a login/sign-in page."""
    url_lower   = page.url.lower()
    title_lower = ""
    try:
        title_lower = page.title().lower()
    except Exception:
        pass

    url_keywords = ["login", "signin", "sign-in", "sign_in", "auth",
                    "authenticate", "logon", "log-in"]
    if any(k in url_lower for k in url_keywords):
        return True

    title_keywords = ["sign in", "log in", "login", "signin"]
    if any(k in title_lower for k in title_keywords):
        return True

    # DOM-based: password field present = login form
    try:
        for sel in _PASSWORD_SELECTORS:
            if page.locator(sel).count() > 0:
                return True
    except Exception:
        pass

    return False


def detect_login_form(page: Page) -> dict:
    """Find all login form elements on the page."""
    result = {
        "email_selector":    None,
        "password_selector": None,
        "submit_selector":   None,
        "is_sso":            False,
        "is_multistep":      False,
        "debug_info":        [],
    }

    # Check for SSO-only pages
    try:
        body_text = page.inner_text("body").lower()
        if any(s in body_text for s in _SSO_INDICATORS):
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
            count = page.locator(sel).count()
            result["debug_info"].append(f"email {sel}: {count}")
            if count > 0:
                result["email_selector"] = sel
                break
        except Exception:
            continue

    # Find password field
    for sel in _PASSWORD_SELECTORS:
        try:
            count = page.locator(sel).count()
            result["debug_info"].append(f"password {sel}: {count}")
            if count > 0:
                result["password_selector"] = sel
                break
        except Exception:
            continue

    # Multi-step detection
    if result["email_selector"] and not result["password_selector"]:
        result["is_multistep"] = True

    # Find submit button
    for sel in _SUBMIT_SELECTORS:
        try:
            count = page.locator(sel).count()
            if count > 0:
                result["submit_selector"] = sel
                result["debug_info"].append(f"submit FOUND: {sel}")
                break
        except Exception:
            continue

    return result


def attempt_login(page: Page, email: str, password: str) -> dict:
    """Attempt to log in using the provided credentials."""
    result = {
        "attempted":   False,
        "success":     False,
        "method":      None,
        "url_before":  page.url,
        "url_after":   None,
        "error":       None,
        "skipped":     False,
        "skip_reason": None,
        "debug":       [],
    }

    if not email or not password:
        result["skipped"]     = True
        result["skip_reason"] = "No credentials configured"
        return result

    if not is_login_page(page):
        result["skipped"]     = True
        result["skip_reason"] = "Not a login page"
        return result

    # Dismiss cookie banners first
    _dismiss_cookie_banner(page)
    page.wait_for_timeout(500)

    form = detect_login_form(page)
    result["debug"] = form.get("debug_info", [])

    if form["is_sso"]:
        result["skipped"]     = True
        result["skip_reason"] = "SSO-only login — skipping"
        return result

    if not form["email_selector"]:
        result["skipped"]     = True
        result["skip_reason"] = f"No email/username field found. Tried: {_EMAIL_SELECTORS[:5]}"
        print(f"[LOGIN] Could not find email field. Debug: {form['debug_info'][:5]}")
        return result

    result["attempted"] = True

    try:
        # Fill email
        print(f"[LOGIN] Filling email field: {form['email_selector']}")
        email_el = page.locator(form["email_selector"]).first
        email_el.scroll_into_view_if_needed(timeout=3000)
        email_el.click(timeout=3000)
        email_el.fill(email)
        time.sleep(0.3)

        # Multi-step: submit email first
        if form["is_multistep"] and form["submit_selector"]:
            print("[LOGIN] Multi-step — submitting email first")
            page.locator(form["submit_selector"]).first.click()
            page.wait_for_timeout(2000)
            form = detect_login_form(page)
            result["method"] = "multistep"

        # Fill password
        if form["password_selector"]:
            print(f"[LOGIN] Filling password field: {form['password_selector']}")
            pwd_el = page.locator(form["password_selector"]).first
            pwd_el.scroll_into_view_if_needed(timeout=3000)
            pwd_el.click(timeout=3000)
            pwd_el.fill(password)
            time.sleep(0.3)
            result["method"] = result["method"] or "standard"
        else:
            result["error"] = "Password field not found"
            return result

        # Submit
        if form["submit_selector"]:
            print(f"[LOGIN] Clicking submit: {form['submit_selector']}")
            page.locator(form["submit_selector"]).first.click()
        else:
            page.locator(form["password_selector"]).first.press("Enter")

        # Wait for navigation
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(2000)

        result["url_after"] = page.url
        result["success"]   = _verify_login_success(page, result["url_before"])

        status = "successful" if result["success"] else "may have failed"
        print(f"[LOGIN] Login {status}! Now at: {page.url}")

    except Exception as e:
        result["error"] = str(e)
        print(f"[LOGIN] Login attempt failed: {e}")

    return result


def _verify_login_success(page: Page, url_before: str) -> bool:
    """Heuristics to detect if login was successful."""
    current_url = page.url
    url_lower   = current_url.lower()

    login_keywords   = ["login", "signin", "sign-in", "auth"]
    was_on_login     = any(k in url_before.lower() for k in login_keywords)
    still_on_login   = any(k in url_lower         for k in login_keywords)

    if was_on_login and not still_on_login:
        return True

    success_keywords = ["dashboard", "home", "profile", "account",
                        "welcome", "overview", "app", "main",
                        "collections", "resume", "builder"]
    if any(k in url_lower for k in success_keywords):
        return True

    # Password field still visible = still on login form = failed
    try:
        if page.locator("input[type='password']:visible").count() > 0:
            # Check for error messages
            for sel in ["[class*='error']:visible", "[role='alert']:visible",
                        ".alert-danger:visible", "[id*='error']:visible"]:
                if page.locator(sel).count() > 0:
                    return False
            return False
    except Exception:
        pass

    return True


def login_if_needed(page: Page) -> dict:
    """Main entry point — auto-detects and attempts login if credentials configured."""
    email    = getattr(CFG, "login_email",    "")
    password = getattr(CFG, "login_password", "")

    if not email or not password:
        return {"skipped": True, "skip_reason": "No LOGIN_EMAIL/LOGIN_PASSWORD in config"}

    if not is_login_page(page):
        return {"skipped": True, "skip_reason": "Not a login page"}

    with allure.step("Smart Login Attempt"):
        result = attempt_login(page, email, password)
        status = "SKIPPED" if result["skipped"] else \
                 ("SUCCESS" if result["success"] else "FAILED")

        print(f"[LOGIN] {status}: "
              f"{result.get('skip_reason') or result.get('error') or result.get('url_after', '')}")

        try:
            allure.attach(
                json.dumps({k: str(v) for k, v in result.items()}, indent=2),
                name=f"Login Result: {status}",
                attachment_type=allure.attachment_type.JSON,
            )
        except Exception:
            pass

        return result
