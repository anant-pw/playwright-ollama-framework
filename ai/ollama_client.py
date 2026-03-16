# ai/ollama_client.py — all config now comes from config.py / config.env
#
# FIX: MODEL is now re-read from environment at health-check time.
# Previously MODEL was set once at import time — before Jenkins env vars
# were fully loaded — causing the configured model to be ignored.

import requests
import allure
import time
import os
from config import CFG

# These are runtime variables — they may be mutated by auto-detect logic
OLLAMA_HOST = CFG.ollama_host
MODEL       = CFG.ollama_model

GENERATE_URL = f"{OLLAMA_HOST}/api/generate"
TAGS_URL     = f"{OLLAMA_HOST}/api/tags"

_health_checked = False


def check_health() -> bool:
    global _health_checked, MODEL, OLLAMA_HOST, GENERATE_URL, TAGS_URL

    if _health_checked:
        return True

    # Re-read model from environment — Jenkins sets this AFTER module import
    env_model = os.environ.get("OLLAMA_MODEL", "").strip()
    if env_model and env_model != MODEL:
        print(f"[OLLAMA] Model updated from env: '{MODEL}' -> '{env_model}'")
        MODEL = env_model

    # Re-read host from environment too
    env_host = os.environ.get("OLLAMA_HOST", "").strip()
    if env_host and env_host != OLLAMA_HOST:
        OLLAMA_HOST  = env_host
        GENERATE_URL = f"{OLLAMA_HOST}/api/generate"
        TAGS_URL     = f"{OLLAMA_HOST}/api/tags"

    try:
        r = requests.get(TAGS_URL, timeout=(CFG.ollama_connect_timeout, 10))
        r.raise_for_status()
        models = [m.get("name", "") for m in r.json().get("models", [])]
        status = f"Ollama healthy ✓\nHost: {OLLAMA_HOST}\nLoaded models: {models}"
        print(f"[OLLAMA] {status}")

        try:
            allure.attach(status, name="Ollama Health Check ✓",
                          attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass

        # Auto-switch only if configured model is truly not found
        if models and not any(MODEL in m for m in models):
            preferred = next((m for m in models if "llama" in m.lower()), models[0])
            auto_model = preferred.split(":")[0]
            print(f"[OLLAMA] '{MODEL}' not found — auto-switching to '{auto_model}'")
            try:
                allure.attach(
                    f"Model '{MODEL}' not found.\nAuto-switched to: '{auto_model}'\nAvailable: {models}",
                    name="⚠ Ollama Model Auto-Switch",
                    attachment_type=allure.attachment_type.TEXT,
                )
            except Exception:
                pass
            MODEL = auto_model
        elif not models:
            print(f"[WARN] No models in Ollama. Run: ollama pull {MODEL}")

        _health_checked = True
        return True

    except requests.exceptions.ConnectionError:
        msg = f"Cannot connect to Ollama at {OLLAMA_HOST}\nRun: ollama serve"
        print(f"[ERROR] {msg}")
        try:
            allure.attach(msg, name="Ollama Health Check ✗",
                          attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass
        return False

    except Exception as e:
        print(f"[WARN] Ollama health check error: {e}")
        return False


def generate(prompt: str, model: str = None, retries: int = None) -> str:
    check_health()

    target_model   = model or MODEL
    total_attempts = (retries if retries is not None else CFG.ollama_retries) + 1
    payload = {"model": target_model, "prompt": prompt, "stream": False}
    last_error = None

    for attempt in range(1, total_attempts + 1):
        try:
            start    = time.time()
            response = requests.post(
                GENERATE_URL,
                json=payload,
                timeout=(CFG.ollama_connect_timeout, CFG.ollama_read_timeout),
            )
            response.raise_for_status()
            text = response.json().get("response", "").strip()
            print(f"[OLLAMA] Response in {time.time()-start:.1f}s ({len(text)} chars)")
            return text

        except requests.exceptions.ConnectionError as e:
            raise OllamaUnavailableError(
                f"Cannot connect to Ollama at {OLLAMA_HOST}. Run `ollama serve`."
            ) from e

        except requests.exceptions.ReadTimeout as e:
            last_error = e
            print(f"[WARN] Ollama timeout after {CFG.ollama_read_timeout}s "
                  f"(attempt {attempt}/{total_attempts})")
            if attempt < total_attempts:
                payload = {"model": target_model,
                           "prompt": prompt[:500] + "\n\nBe very brief.",
                           "stream": False}
                time.sleep(2)

        except Exception as e:
            last_error = e
            print(f"[WARN] Ollama request failed (attempt {attempt}): {e}")
            if attempt < total_attempts:
                time.sleep(2)

    print(f"[WARN] Ollama gave up after {total_attempts} attempt(s): {last_error}")
    return ""


class OllamaUnavailableError(Exception):
    pass
