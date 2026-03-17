# AI-Powered Autonomous Testing Framework (Playwright + Python)

## Overview

This project is a learning-driven prototype to explore how AI can be used in test automation beyond traditional scripted approaches.

Instead of relying only on predefined test cases, the framework attempts to:

* Observe the application
* Decide what to do next using AI
* Perform exploratory-style testing
* Capture and report findings

This is not a production-ready framework, but a working experiment to understand practical implementation.

---

## Features

* Dynamic DOM understanding
* AI-driven action decisions
* Basic exploratory testing flow
* AI-assisted bug detection (not only assertions)
* Screenshot-based visual validation
* Automatic bug reporting
* Test case generation in Excel
* Basic exploration memory tracking
* Allure reporting integration
* Jenkins-ready execution

---

## Tech Stack

* Python
* Playwright
* Pytest
* Allure Reports
* Ollama (LLM integration)
* Pandas / OpenPyXL (Excel handling)

---

## Project Structure (High Level)

```
ai_tester_project/
│
├── ai/                # AI logic (decision making, bug detection)
├── browser/           # Playwright actions, DOM extraction, screenshots
├── reporting/         # Bug reports, test case generation
├── config/            # Environment/config files
├── tests/             # Test execution files
├── run_agents.py      # Entry point
└── requirements.txt
```

---

## Setup Instructions

### 1. Clone the repository

```
git clone <your-repo-link>
cd ai_tester_project
```

### 2. Create virtual environment

```
python -m venv venv
venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Install Playwright browsers

```
playwright install
```

### 5. Start Ollama (required for AI)

Make sure Ollama is running locally.

Example:

```
ollama run llama3
```

---

## Running the Framework

```
pytest run_agents.py --headed -s --alluredir=allure-results
```

### View Allure Report

```
allure serve allure-results
```

---

## Jenkins Integration

This project is Jenkins-ready.

Basic steps:

1. Configure job with project path
2. Install dependencies in build step
3. Run pytest command
4. Publish Allure results

---

## What This Project Tries to Explore

* Can AI guide test execution instead of fixed scripts?
* Can we detect bugs without explicit assertions?
* How far can exploratory testing be automated?

---

## Limitations

* AI decisions are not always consistent
* Requires tuning of prompts and inputs
* Not suitable for production use yet
* Visual validation is basic (screenshot-based)

---

## Future Improvements

* Risk-based intelligent exploration
* Better visual comparison (baseline vs diff)
* Improved bug classification
* More stable AI decision-making

---

## Note

This project was built as a learning exercise with the help of AI tools and references. The goal was to understand integration and workflow rather than build everything from scratch.

---

## Contributions / Feedback

Feel free to explore, raise issues, or share suggestions.
