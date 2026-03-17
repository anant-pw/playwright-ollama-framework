pipeline {
    agent any
    
    parameters {
        string(name: 'TARGET_URLS', defaultValue: 'https://example.com', description: 'URLs to test')
        choice(name: 'BROWSER', choices: ['chromium', 'firefox', 'webkit'], description: 'Browser')
    }
    
    stages {
        stage('Setup') {
            steps {
                bat 'python --version'
                bat 'pip install -r requirements.txt'
                bat 'playwright install'
                bat 'set PYTHONIOENCODING=utf-8'
                bat 'set PYTHONUNBUFFERED=1'
                // Pass parameters to tests
                bat "set TARGET_URLS=%TARGET_URLS%"
                bat "set BROWSER=%BROWSER%"
            }
        }
        
        stage('Test') {
            steps {
                bat 'python.exe -X utf8 -m pytest --alluredir=allure-results -v'
            }
        }
    }
    
    // THIS RUNS NO MATTER WHAT (pass/fail)
    post {
        always {
            script {
                echo "🔥 Generating ALL reports..."
                
                // 1. Allure Report (Main Dashboard)
                allure([
                    includeProperties: false,
                    jdk: '',
                    results: [[path: 'allure-results']]
                ])
                
                // 2. Test Cases Viewer (🧪 TC Dashboard)
                publishHTML([
                    allowMissing: true,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'generated_test_cases',
                    reportFiles: '**/*.html',
                    reportName: '🧪 Test Cases Viewer'
                ])
                
                // 3. Bug Reports Viewer (🐛 Bug Dashboard)
                publishHTML([
                    allowMissing: true,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'bug_reports',
                    reportFiles: '**/*.html',
                    reportName: '🐛 Bug Reports'
                ])
                
                // 4. Archive ALL files (Excel + Screenshots)
                archiveArtifacts(
                    artifacts: 'allure-results/**, generated_test_cases/**, bug_reports/**, screenshots/**, *.xlsx',
                    allowEmptyArchive: true,
                    fingerprint: true
                )
                
                echo "✅ Dashboard ready! Check links above."
            }
        }
    }
}
