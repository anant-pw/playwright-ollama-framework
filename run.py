#!/usr/bin/env python3
"""
run.py — clean + run + open report in one command.
Usage:
    python run.py                   # run everything
    python run.py run_agents.py     # agent entry point only
    python run.py tests/            # test suite only
"""
import subprocess, shutil, sys, os, platform
from config import CFG

RESULTS = CFG.allure_results_dir
REPORT  = CFG.allure_report_dir


def clean():
    for d in [RESULTS, REPORT]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        print(f"[CLEAN] {d}/ ready")


def run_pytest(targets):
    cmd = ["pytest", "--alluredir", RESULTS, "--clean-alluredir", "-v", "-s"] + targets
    print(f"\n[RUN] {' '.join(cmd)}\n")
    return subprocess.run(cmd).returncode


def open_report():
    gen = subprocess.run(
        ["allure", "generate", RESULTS, "--clean", "-o", REPORT],
        capture_output=True, text=True,
    )
    if gen.returncode != 0:
        subprocess.Popen(["allure", "serve", RESULTS])
        return
    index = os.path.abspath(os.path.join(REPORT, "index.html"))
    print(f"\n[REPORT] {index}")
    {"Windows": os.startfile, "Darwin": lambda p: subprocess.Popen(["open", p]),
     }.get(platform.system(), lambda p: subprocess.Popen(["xdg-open", p]))(index)


if __name__ == "__main__":
    clean()
    code = run_pytest(sys.argv[1:])
    open_report()
    sys.exit(code)
