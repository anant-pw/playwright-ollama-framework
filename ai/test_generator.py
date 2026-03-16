# ai/test_generator.py
#
# IMPROVEMENT: Context-aware TC generation.
# Old prompt ignored what was actually ON the page — generated same 5 generic TCs
# for every URL. New prompt explicitly uses form fields, buttons, and page type
# to generate TCs that are actually specific and testable.

import allure
from ai.ollama_client import generate, OllamaUnavailableError
from reporting.testcase_writer import save_test_cases


def generate_test_cases(page_text: str, url: str,
                        buttons: list = None,
                        inputs: list  = None,
                        links: list   = None,
                        page_title: str = "") -> str:
    """
    Generate test cases specific to what's actually on this page.
    Now accepts page elements so TCs reference real UI components.
    """

    # Build a compact page summary for the prompt
    elements_summary = []
    if inputs:
        elements_summary.append(f"Input fields: {inputs[:10]}")
    if buttons:
        elements_summary.append(f"Buttons: {[b for b in buttons[:10] if b.strip()]}")
    if links:
        elements_summary.append(f"Links: {[l for l in links[:8] if l.strip()]}")

    page_type_hint = _guess_page_type(url, page_text, buttons, inputs)

    prompt = f"""You are a senior QA engineer writing test cases for a {page_type_hint}.

URL: {url}
Page title: {page_title or 'unknown'}

ACTUAL PAGE ELEMENTS:
{chr(10).join(elements_summary) if elements_summary else 'No elements detected'}

PAGE CONTENT SAMPLE:
{page_text[:1500]}

Write exactly 5 test cases that TEST THE SPECIFIC FUNCTIONALITY on this page.
Reference actual button names, field names, and features you can see above.

Rules:
- Each TC must be specific to THIS page, not generic
- Reference actual element names from the page (e.g. "Email field", "Sign In button")
- Cover: happy path, validation, edge cases, error states
- NO generic TCs like "Verify page loads" or "Check page title"

Return ONLY lines in this format, nothing else:
Title | Steps | Expected Result
"""

    with allure.step("Generate AI test cases"):
        allure.attach(prompt, name="TC Generation Prompt",
                      attachment_type=allure.attachment_type.TEXT)

        try:
            ai_output = generate(prompt)
            if not ai_output:
                raise ValueError("Empty response")
        except (OllamaUnavailableError, ValueError) as e:
            print(f"[WARN] TC generation fallback ({e})")
            ai_output = _fallback_tcs(url, page_type_hint, inputs, buttons)

        allure.attach(ai_output, name="AI Raw TC Output",
                      attachment_type=allure.attachment_type.TEXT)

    with allure.step("Save TCs"):
        saved = save_test_cases(ai_output, url)
        print(f"[TC] {len(saved)} test case(s) generated for {page_type_hint}")

    return ai_output


def _guess_page_type(url: str, page_text: str, buttons: list, inputs: list) -> str:
    """Guess the page type so the prompt is more targeted."""
    url_lower    = url.lower()
    text_lower   = page_text.lower()[:500]
    inputs_lower = " ".join(str(i) for i in (inputs or [])).lower()

    if any(k in url_lower for k in ["login", "signin", "sign-in"]):
        return "login / sign-in page"
    if any(k in url_lower for k in ["register", "signup", "sign-up", "create-account"]):
        return "registration page"
    if any(k in url_lower for k in ["checkout", "payment", "billing"]):
        return "checkout / payment page"
    if any(k in url_lower for k in ["search", "results", "find"]):
        return "search results page"
    if any(k in url_lower for k in ["profile", "account", "settings"]):
        return "user profile / settings page"
    if any(k in url_lower for k in ["dashboard", "home", "overview"]):
        return "dashboard page"
    if any(k in text_lower for k in ["password", "email"]) and inputs:
        return "authentication page"
    if any(k in text_lower for k in ["cart", "basket", "order"]):
        return "shopping cart page"
    return "web page"


def _fallback_tcs(url: str, page_type: str,
                  inputs: list, buttons: list) -> str:
    """Specific fallback TCs based on page type when Ollama is unavailable."""
    input_names  = [str(i) for i in (inputs  or []) if str(i).strip()][:3]
    button_names = [str(b) for b in (buttons or []) if str(b).strip()][:3]

    if "login" in page_type or "auth" in page_type:
        return (
            f"Login with valid credentials | Enter valid email and password, click sign in | User is logged in and redirected\n"
            f"Login with invalid password | Enter valid email and wrong password | Error message shown, user stays on page\n"
            f"Login with empty email | Leave email blank, click sign in | Validation error shown for email field\n"
            f"Login with empty password | Enter email, leave password blank | Validation error shown for password field\n"
            f"Login with invalid email format | Enter 'notanemail', click sign in | Email format validation error shown"
        )
    if "register" in page_type:
        return (
            f"Register with valid data | Fill all required fields with valid data | Account created, redirect to dashboard\n"
            f"Register with existing email | Use already-registered email | Error: email already exists\n"
            f"Register with mismatched passwords | Enter different values in password fields | Mismatch error shown\n"
            f"Register with weak password | Enter short/simple password | Password strength error shown\n"
            f"Register with missing required fields | Submit form with blank fields | Required field errors shown"
        )
    # Generic but element-aware fallback
    first_input  = input_names[0]  if input_names  else "input field"
    first_button = button_names[0] if button_names else "submit button"
    return (
        f"Submit form with valid data | Fill {first_input} with valid data, click {first_button} | Form submits successfully\n"
        f"Submit form with empty fields | Leave {first_input} blank, click {first_button} | Validation errors shown\n"
        f"Verify page elements present | Load {url} | All expected elements are visible\n"
        f"Verify error handling | Enter invalid data in {first_input} | Appropriate error message displayed\n"
        f"Verify responsive behaviour | Resize browser window while on {url} | Layout adapts without overflow"
    )
