// Jenkinsfile
// ─────────────────────────────────────────────────────────────────────────────
// Pipeline for AI Test Framework
// Assumes:
//   - Jenkins agent is Windows (your current machine) OR Linux
//   - Python venv is at D:\ai_tester_project\venv  (Windows)
//     or  /opt/ai_tester/venv                      (Linux)
//   - Ollama is running as a service on the same machine
//   - Allure Jenkins plugin is installed
// ─────────────────────────────────────────────────────────────────────────────

pipeline {

    agent any

    // ── Parameters — change these per-run from Jenkins UI ──────────────────
    parameters {
        string(
            name:         'TARGET_URLS',
            defaultValue: 'https://myperfectresume.com/signin',
            description:  'Comma-separated URLs to test'
        )
        choice(
            name:         'BROWSER',
            choices:      ['chromium', 'firefox', 'webkit'],
            description:  'Browser to use'
        )
        string(
            name:         'MAX_STEPS',
            defaultValue: '5',
            description:  'Exploration steps per URL'
        )
        string(
            name:         'OLLAMA_MODEL',
            defaultValue: 'llama3',
            description:  'Ollama model name'
        )
        booleanParam(
            name:         'SEND_EMAIL',
            defaultValue: false,
            description:  'Send email report after run'
        )
    }

    // ── Environment — override config.env values via Jenkins env vars ───────
    environment {
        TARGET_URLS             = "${params.TARGET_URLS}"
        BROWSER                 = "${params.BROWSER}"
        MAX_STEPS               = "${params.MAX_STEPS}"
        OLLAMA_MODEL            = "${params.OLLAMA_MODEL}"
        HEADLESS                = "true"          // always headless in CI
        OLLAMA_HOST             = "http://localhost:11434"
        OLLAMA_READ_TIMEOUT     = "300"
        OLLAMA_CONNECT_TIMEOUT  = "10"
        OLLAMA_RETRIES          = "2"
        ALLURE_RESULTS_DIR      = "allure-results"
        ALLURE_REPORT_DIR       = "allure-report"
        BUG_REPORTS_DIR         = "bug_reports"
        SCREENSHOTS_DIR         = "screenshots"
        TC_FILE                 = "generated_test_cases.xlsx"
        PYTHONUNBUFFERED        = "1"             // show print() in real time
    }

    options {
        // Keep last 10 builds
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // Fail if entire pipeline takes more than 2 hours
        timeout(time: 2, unit: 'HOURS')
        // Add timestamps to every log line
        timestamps()
        // Don't run two builds at the same time (Ollama is single-threaded)
        disableConcurrentBuilds()
    }

    stages {

        // ── 1. Checkout ──────────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                echo "Checking out source code..."
                checkout scm
                // Show what commit we're on
                script {
                    if (isUnix()) {
                        sh 'git log --oneline -5'
                    } else {
                        bat 'git log --oneline -5'
                    }
                }
            }
        }

        // ── 2. Setup Python environment ──────────────────────────────────────
        stage('Setup Python') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            python3 -m venv venv
                            . venv/bin/activate
                            pip install --upgrade pip --quiet
                            pip install -r requirements.txt --quiet
                            playwright install chromium firefox webkit
                            playwright install-deps
                        '''
                    } else {
                        bat '''
                            python -m venv venv
                            call venv\\Scripts\\activate.bat
                            pip install --upgrade pip --quiet
                            pip install -r requirements.txt --quiet
                            playwright install chromium firefox webkit
                        '''
                    }
                }
            }
        }

        // ── 3. Check Ollama is running ───────────────────────────────────────
        stage('Check Ollama') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            curl -sf http://localhost:11434/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
print('Ollama models available:', models)
if not models:
    print('ERROR: No models loaded. Run: ollama pull llama3')
    sys.exit(1)
"
                        '''
                    } else {
                        bat '''
                            curl -sf http://localhost:11434/api/tags > ollama_check.json
                            python -c "
import json
with open('ollama_check.json') as f: data = json.load(f)
models = [m['name'] for m in data.get('models', [])]
print('Ollama models:', models)
if not models:
    print('ERROR: No models loaded')
    exit(1)
"
                        '''
                    }
                }
            }
        }

        // ── 4. Run Tests ─────────────────────────────────────────────────────
        stage('Run AI Tests') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            . venv/bin/activate
                            pytest run_agents.py tests/ \
                                --alluredir=allure-results \
                                --clean-alluredir \
                                -v -s \
                                --tb=short \
                                2>&1 | tee pytest_output.txt
                        '''
                    } else {
                        bat '''
                            call venv\\Scripts\\activate.bat
                            pytest run_agents.py tests/ ^
                                --alluredir=allure-results ^
                                --clean-alluredir ^
                                -v -s ^
                                --tb=short ^
                                2>&1 | tee pytest_output.txt
                        '''
                    }
                }
            }
            // Don't fail the pipeline just because tests failed —
            // we still want to publish the report
            post {
                always {
                    echo "Tests complete. Publishing artifacts..."
                }
            }
        }

        // ── 5. Archive artifacts ─────────────────────────────────────────────
        stage('Archive Artifacts') {
            steps {
                // Archive screenshots, bug reports, TC file
                archiveArtifacts artifacts: 'screenshots/**/*.png',
                                 allowEmptyArchive: true
                archiveArtifacts artifacts: 'bug_reports/**/*.json',
                                 allowEmptyArchive: true
                archiveArtifacts artifacts: 'bug_reports/bug_report_viewer.html',
                                 allowEmptyArchive: true
                archiveArtifacts artifacts: 'generated_test_cases.xlsx',
                                 allowEmptyArchive: true
                archiveArtifacts artifacts: 'pytest_output.txt',
                                 allowEmptyArchive: true
            }
        }
    }

    // ── Post-pipeline actions ─────────────────────────────────────────────────
    post {

        always {
            // Publish Allure report — requires "Allure Jenkins Plugin"
            allure([
                includeProperties: true,
                jdk:               '',
                results:           [[path: 'allure-results']]
            ])

            // Clean workspace to save disk space (keeps archived artifacts)
            cleanWs(
                cleanWhenSuccess:  false,   // keep on success for debugging
                cleanWhenFailure:  false,
                cleanWhenAborted:  true,
                deleteDirs:        true,
                patterns: [
                    [pattern: 'venv/**', type: 'INCLUDE'],
                    [pattern: '__pycache__/**', type: 'INCLUDE'],
                    [pattern: '*.pyc', type: 'INCLUDE'],
                ]
            )
        }

        success {
            echo "All tests PASSED"
            script {
                if (params.SEND_EMAIL) {
                    emailext(
                        subject: "✅ AI Tests PASSED — Build #${BUILD_NUMBER}",
                        body:    """
Build #${BUILD_NUMBER} completed successfully.
URL tested: ${params.TARGET_URLS}
Browser: ${params.BROWSER}

Allure Report: ${BUILD_URL}allure
Artifacts: ${BUILD_URL}artifact
                        """,
                        to: '${DEFAULT_RECIPIENTS}'
                    )
                }
            }
        }

        failure {
            echo "Tests FAILED — check Allure report for details"
            script {
                if (params.SEND_EMAIL) {
                    emailext(
                        subject: "❌ AI Tests FAILED — Build #${BUILD_NUMBER}",
                        body:    """
Build #${BUILD_NUMBER} FAILED.
URL tested: ${params.TARGET_URLS}

Allure Report: ${BUILD_URL}allure
Console log:  ${BUILD_URL}console
                        """,
                        to: '${DEFAULT_RECIPIENTS}'
                    )
                }
            }
        }

        unstable {
            echo "Tests UNSTABLE — some tests failed, check Allure report"
        }
    }
}
