# brain/decision_engine.py
#
# IMPROVEMENT: AI now returns specific element targets, not just action type.
# Old: "click_button" — always hit first button regardless
# New: "click_button:Sign In" — hits the specific intended element

import allure
from ai.ollama_client import generate, OllamaUnavailableError


def decide_next_action(page_text: str, buttons: list, links: list,
                       inputs: list, memory: list,
                       page_title: str = "", current_url: str = "") -> str:
    """
    Returns a specific action+target string.
    Format: "action_type:target_text"
    e.g. "click_button:Sign In", "type_input:email:test@example.com", "scroll", "stop"
    """
    # Filter empty elements
    clean_buttons = [b.strip() for b in (buttons or []) if b.strip()][:10]
    clean_links   = [l.strip() for l in (links   or []) if l.strip()][:10]
    clean_inputs  = [i.strip() for i in (inputs  or []) if str(i).strip()][:10]

    prompt = f"""You are a QA testing agent deciding what to do next on this web page.

URL: {current_url}
Page title: {page_title}

AVAILABLE BUTTONS: {clean_buttons}
AVAILABLE LINKS: {clean_links}  
AVAILABLE INPUT FIELDS: {clean_inputs}

ACTIONS ALREADY TAKEN (don't repeat these):
{memory[-5:] if memory else 'none yet'}

PAGE CONTENT SAMPLE:
{page_text[:1000]}

Choose the MOST USEFUL next testing action. Pick the action that will:
1. Test important functionality (forms, auth, navigation)
2. Cover something not yet tested
3. Be likely to reveal bugs

Respond with EXACTLY ONE line in this format:
action_type:target

Where action_type is one of: click_button | click_link | type_input | scroll | stop
And target is the SPECIFIC element name from the lists above.

Examples of correct responses:
click_button:Sign In
click_link:Forgot Password  
type_input:email:test@example.com
type_input:password:TestPass123
scroll:400
stop

Respond with ONLY the action line, nothing else.
"""

    with allure.step("AI decision engine"):
        try:
            allure.attach(prompt, name="Decision Prompt",
                          attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass

        try:
            decision = generate(prompt)
            if not decision:
                decision = "stop"
        except OllamaUnavailableError:
            decision = "stop"

        # Clean up — take only the first line
        decision = decision.strip().split("\n")[0].strip()

        # Validate format — if AI returned something unexpected, parse it
        if not any(decision.startswith(a) for a in
                   ["click_button", "click_link", "type_input", "scroll", "stop"]):
            # Try to extract an action keyword from the response
            for keyword in ["click_button", "click_link", "type_input", "scroll", "stop"]:
                if keyword in decision.lower():
                    decision = keyword
                    break
            else:
                decision = "stop"

        try:
            allure.attach(decision, name="AI Decision",
                          attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass

    return decision
