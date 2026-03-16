# Jenkins Integration — Step by Step

## Prerequisites checklist

Before starting, confirm you have:
- [ ] Jenkins installed and running (http://localhost:8080 or your server)
- [ ] Python 3.9+ installed on the Jenkins machine
- [ ] Git installed on the Jenkins machine
- [ ] Ollama running as a service (`ollama serve`)
- [ ] Your project in a Git repo (GitHub / GitLab / Bitbucket / local)

---

## Step 1 — Install Jenkins plugins

Go to **Jenkins → Manage Jenkins → Plugins → Available plugins**
Search and install these (tick all, then Install):

| Plugin | Why |
|--------|-----|
| **Allure Jenkins Plugin** | Publishes Allure HTML report on each build page |
| **Pipeline** | Enables Jenkinsfile pipeline jobs |
| **Git** | Clones your repo |
| **Workspace Cleanup** | Cleans temp files after build |
| **Timestamper** | Adds timestamps to console output |
| **Email Extension** | Sends pass/fail emails (optional) |

Restart Jenkins after installing.

---

## Step 2 — Configure Allure plugin

Go to **Jenkins → Manage Jenkins → Tools**

Scroll to **Allure Commandline** section:
1. Click **Add Allure Commandline**
2. Name: `allure`
3. Tick **Install automatically**
4. Version: pick latest (2.27.0+)
5. Click **Save**

> This is what the `allure([...])` step in the Jenkinsfile uses.
> If you already have Allure CLI installed, you can point to that instead.

---

## Step 3 — Push your project to Git

If not already in Git:
```bash
cd D:\ai_tester_project
git init
git add .
git commit -m "Initial commit — AI test framework"
```

For a remote repo (GitHub example):
```bash
git remote add origin https://github.com/YOUR_USERNAME/ai-test-framework.git
git push -u origin main
```

> If you want to run locally without a remote repo, skip the push —
> Jenkins can use a local folder path as the repo (see Step 4b).

---

## Step 4 — Create the Jenkins Pipeline job

### Option A — From a Git repo (recommended)

1. Jenkins home → **New Item**
2. Name: `AI-Test-Framework`
3. Select **Pipeline** → OK
4. In the job config:
   - **General** → tick `This project is parameterized` (parameters are already in the Jenkinsfile)
   - **Build Triggers** → tick `Poll SCM`, schedule: `H 9 * * 1-5` (runs at 9am Mon–Fri)
   - **Pipeline** section:
     - Definition: **Pipeline script from SCM**
     - SCM: **Git**
     - Repository URL: `https://github.com/YOUR_USERNAME/ai-test-framework.git`
     - Branch: `*/main`
     - Script Path: `Jenkinsfile`
5. Click **Save**

### Option B — Local folder (no Git remote needed)

Same as above but:
- SCM: **Git**
- Repository URL: `file:///D:/ai_tester_project`
- This uses your local folder directly

### Option C — Paste script directly

1. Pipeline section → Definition: **Pipeline script**
2. Paste the contents of `Jenkinsfile` directly
3. Click Save
> Note: with this option you must manually update the script when code changes.

---

## Step 5 — Configure Ollama to run as a Windows Service

Jenkins runs in the background — Ollama needs to be running when Jenkins
triggers a build at 9am, even if nobody is logged in.

### Windows — run Ollama as a service with NSSM

1. Download NSSM from https://nssm.cc/download
2. Open Command Prompt as Administrator:
```cmd
nssm install OllamaService "C:\Users\YOUR_USER\AppData\Local\Programs\Ollama\ollama.exe"
nssm set OllamaService AppParameters "serve"
nssm set OllamaService Start SERVICE_AUTO_START
nssm start OllamaService
```
3. Verify: `curl http://localhost:11434/api/tags`

> After this, Ollama starts automatically with Windows — no manual start needed.

---

## Step 6 — Configure the Jenkins agent (Windows-specific)

Jenkins by default runs as the SYSTEM account which can't access your user's
Python venv or Ollama. Fix this:

1. **Jenkins → Manage Jenkins → Security → Agents**
2. If using the built-in node:
   - Go to **Manage Jenkins → Nodes → Built-In Node → Configure**
   - Set **# of executors** to 1 (Ollama is single-threaded)
3. Run Jenkins under your user account:
   - Open **Services** (services.msc)
   - Find **Jenkins**
   - Right-click → Properties → Log On tab
   - Switch from "Local System" to "This account"
   - Enter your Windows username and password
   - Restart Jenkins service

---

## Step 7 — First build

1. Go to your `AI-Test-Framework` job
2. Click **Build with Parameters**
3. Set:
   - TARGET_URLS: `https://myperfectresume.com/signin`
   - BROWSER: `chromium`
   - MAX_STEPS: `2` (use 2 for the first test run — faster)
   - OLLAMA_MODEL: `llama3`
4. Click **Build**
5. Click the build number → **Console Output** to watch live

---

## Step 8 — View the Allure report in Jenkins

After the build completes:
- Build page → **Allure Report** link (appears automatically after first run)
- Or: `http://YOUR_JENKINS/job/AI-Test-Framework/LAST_BUILD_NUMBER/allure`

The report shows:
- Overview: pass/fail donut
- Behaviors: TCs grouped by Feature/Story
- Suites: every TC and bug as individual test cases
- Categories: bugs grouped by severity
- Environment: browser, URL, model used

---

## Step 9 — Schedule automatic runs

In the job config → **Build Triggers**:

| Schedule | Cron |
|----------|------|
| Every day at 9am | `H 9 * * *` |
| Mon–Fri at 9am | `H 9 * * 1-5` |
| Every 6 hours | `H */6 * * *` |
| On every Git push | tick `GitHub hook trigger` or `GitLab webhook` |

---

## Troubleshooting

**"venv not found" / pip errors**
→ Make sure Python is in PATH for the Jenkins user account:
```
System Properties → Environment Variables → Path → Add Python install dir
```

**"playwright not found" / browser launch fails**
→ Run in Jenkins console:
```bat
call venv\Scripts\activate.bat && playwright install chromium
```

**"Ollama unavailable" in build**
→ Check OllamaService is running: `sc query OllamaService`
→ Test: `curl http://localhost:11434/api/tags`

**"allure: command not found"**
→ Allure plugin auto-installs it — check Jenkins → Tools → Allure Commandline
→ Or install manually and add to PATH

**Allure report shows but is empty**
→ `allure-results/` must exist and have `.json` files before `allure([...])` runs
→ Check the "Archive Artifacts" stage output for `allure-results`

**Build passes but no report link**
→ Must have Allure Jenkins Plugin installed AND configured in Tools (Step 2)

---

## Environment variables you can override per-build

All values in `config.env` can be overridden as Jenkins parameters:

```
TARGET_URLS            → which site to test
BROWSER                → chromium / firefox / webkit  
MAX_STEPS              → depth of exploration
OLLAMA_MODEL           → which AI model
HEADLESS               → always true in CI (set in Jenkinsfile)
OLLAMA_READ_TIMEOUT    → increase if model is slow
```

These are passed as environment variables from the Jenkinsfile and
`config.py` picks them up automatically — no code changes needed.
