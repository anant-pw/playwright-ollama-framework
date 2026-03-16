# ai/ai_client.py

import allure
from ai.ollama_client import generate, OllamaUnavailableError


def ask_ai(page_text: str,
           buttons: list = None,
           links: list   = None,
           inputs: list  = None,
           history: list = None) -> str:

    prompt = f"""You are an autonomous QA testing agent analysing a web page.

Page Content:
{page_text[:3000]}

Buttons: {buttons or []}
Links:   {links or []}
Inputs:  {inputs or []}
Previous Actions: {history or []}

Decide the single best next testing action.
Reply with ONE keyword only: click_button | click_link | type_input | scroll | stop
"""

    try:
        allure.attach(prompt, name="AI Prompt",
                      attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass

    try:
        result = generate(prompt)
        if not result:
            result = "stop"
    except OllamaUnavailableError as e:
        print(f"[ERROR] {e}")
        result = "stop"

    try:
        allure.attach(result, name="AI Response",
                      attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass

    return result
