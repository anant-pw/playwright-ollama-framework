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
                // FIX: Set UTF-8 encoding for Python console
                bat 'set PYTHONIOENCODING=utf-8'
                bat 'set PYTHONUNBUFFERED=1'
            }
        }
        
        stage('Test') {
            steps {
                bat 'python.exe -X utf8 -m pytest --alluredir=allure-results -v'
            
            }
        }
        
        stage('Report') {
            steps {
                allure includeProperties: false, 
                       results: [[path: 'allure-results']]
            }
            post {
                always {
                    // Generate Allure report EVEN ON FAILURE
                    allure([
                        includeProperties: false,
                        jdk: '',
                        results: [[path: 'allure-results']]
                    ])
                }
            }
        }
    }
}
