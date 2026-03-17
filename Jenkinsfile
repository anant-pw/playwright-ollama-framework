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
                // Generate Allure Report
                allure([
                    includeProperties: false,
                    jdk: '',
                    results: [[path: 'allure-results']]
                ])
                
                // Publish HTML reports
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'allure-report',
                    reportFiles: 'index.html',
                    reportName: 'Allure Report'
                ])
                
                // Archive artifacts
                archiveArtifacts artifacts: 'allure-results/**, bug_reports/**, screenshots/**', 
                               allowEmptyArchive: true
            }
        }
    }
}
