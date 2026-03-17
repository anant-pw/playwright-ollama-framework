# config.py — Central configuration loader.
# PHASE 1: Added login credentials support

import os
from pathlib import Path
from dataclasses import dataclass, field

_ENV_FILE = Path(__file__).parent / "config.env"

def _load_env_file(path: Path) -> None:
    if not path.exists():
        print(f"[CONFIG] config.env not found — using defaults / environment vars.")
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value

_load_env_file(_ENV_FILE)

def _env(k, d=""): return os.environ.get(k, d).strip()
def _env_int(k, d):
    try: return int(os.environ.get(k, str(d)))
    except: return d
def _env_bool(k, d):
    return os.environ.get(k, str(d)).strip().lower() in ("1","true","yes","on")
def _env_list(k, d):
    raw = os.environ.get(k, "")
    return [i.strip() for i in raw.split(",") if i.strip()] if raw else d


@dataclass
class Config:
    # URLs
    target_urls: list = field(default_factory=lambda: ["https://example.com"])

    # Browser
    headless:         bool = True
    browser:          str  = "chromium"
    max_steps:        int  = 5
    page_timeout:     int  = 60_000

    # Stealth
    user_agent:       str  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/123.0.0.0 Safari/537.36")
    viewport_width:   int  = 1280
    viewport_height:  int  = 800
    locale:           str  = "en-US"
    timezone:         str  = "America/New_York"

    # ── NEW: Login credentials ───────────────────────────────────────────────
    login_email:    str = ""   # Set LOGIN_EMAIL in config.env
    login_password: str = ""   # Set LOGIN_PASSWORD in config.env
    login_url:      str = ""   # Optional: specific login URL to navigate to first

    # Ollama
    ollama_host:             str = "http://localhost:11434"
    ollama_model:            str = "llama3"
    ollama_read_timeout:     int = 300
    ollama_connect_timeout:  int = 5
    ollama_retries:          int = 1

    # Reporting
    allure_results_dir: str = "allure-results"
    allure_report_dir:  str = "allure-report"
    bug_reports_dir:    str = "bug_reports"
    screenshots_dir:    str = "screenshots"
    tc_file:            str = "generated_test_cases.xlsx"

    def browser_context_kwargs(self) -> dict:
        return {
            "user_agent":          self.user_agent,
            "viewport":            {"width": self.viewport_width, "height": self.viewport_height},
            "locale":              self.locale,
            "timezone_id":         self.timezone,
            "java_script_enabled": True,
            "accept_downloads":    False,
            "ignore_https_errors": True,
        }

    def browser_launch_kwargs(self) -> dict:
        return {
            "headless": self.headless,
            "args": [
                "--disable-http2",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--ignore-certificate-errors",
                "--disable-web-security",
            ],
        }

    def summary(self) -> str:
        login_status = (
            f"  Login Email     : {self.login_email or '(not configured)'}\n"
            f"  Login Password  : {'***' if self.login_password else '(not configured)'}\n"
        )
        lines = [
            "=" * 58,
            "  AI FRAMEWORK - ACTIVE CONFIGURATION",
            "=" * 58,
            f"  Target URLs       : {', '.join(self.target_urls)}",
            f"  Browser           : {self.browser}  (headless={self.headless})",
            f"  Max steps/URL     : {self.max_steps}",
            f"  Page timeout      : {self.page_timeout}ms",
            f"  User-Agent        : {self.user_agent[:60]}...",
            f"  Viewport          : {self.viewport_width}x{self.viewport_height}",
            f"  Locale / TZ       : {self.locale} / {self.timezone}",
            "-" * 58,
            f"  Ollama host       : {self.ollama_host}",
            f"  Ollama model      : {self.ollama_model}",
            f"  Read timeout      : {self.ollama_read_timeout}s",
            f"  Retries           : {self.ollama_retries}",
            "-" * 58,
            login_status.rstrip(),
            "-" * 58,
            f"  Allure results    : {self.allure_results_dir}/",
            f"  Bug reports       : {self.bug_reports_dir}/",
            f"  Screenshots       : {self.screenshots_dir}/",
            f"  TC Excel file     : {self.tc_file}",
            "=" * 58,
        ]
        return "\n".join(lines)


CFG = Config(
    target_urls            = _env_list("TARGET_URLS", ["https://example.com"]),
    headless               = _env_bool("HEADLESS",    True),
    browser                = _env("BROWSER",          "chromium"),
    max_steps              = _env_int("MAX_STEPS",    5),
    page_timeout           = _env_int("PAGE_TIMEOUT", 60_000),
    user_agent             = _env("USER_AGENT", (
                                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                                 "Chrome/123.0.0.0 Safari/537.36")),
    viewport_width         = _env_int("VIEWPORT_WIDTH",  1280),
    viewport_height        = _env_int("VIEWPORT_HEIGHT", 800),
    locale                 = _env("LOCALE",   "en-US"),
    timezone               = _env("TIMEZONE", "America/New_York"),

    # NEW login credentials
    login_email            = _env("LOGIN_EMAIL",    ""),
    login_password         = _env("LOGIN_PASSWORD", ""),
    login_url              = _env("LOGIN_URL",       ""),

    ollama_host            = _env("OLLAMA_HOST",               "http://localhost:11434"),
    ollama_model           = _env("OLLAMA_MODEL",              "llama3"),
    ollama_read_timeout    = _env_int("OLLAMA_READ_TIMEOUT",    300),
    ollama_connect_timeout = _env_int("OLLAMA_CONNECT_TIMEOUT", 5),
    ollama_retries         = _env_int("OLLAMA_RETRIES",         1),
    allure_results_dir     = _env("ALLURE_RESULTS_DIR", "allure-results"),
    allure_report_dir      = _env("ALLURE_REPORT_DIR",  "allure-report"),
    bug_reports_dir        = _env("BUG_REPORTS_DIR",    "bug_reports"),
    screenshots_dir        = _env("SCREENSHOTS_DIR",    "screenshots"),
    tc_file                = _env("TC_FILE",             "generated_test_cases.xlsx"),
)

print("\n" + CFG.summary() + "\n")
