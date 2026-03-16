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
            }
        }
        
        stage('Test') {
            steps {
                bat """
                    set TARGET_URLS=%TARGET_URLS%
                    set BROWSER=%BROWSER%
                    pytest --alluredir=allure-results -v
                """
            }
        }
        
        stage('Report') {
            steps {
                allure includeProperties: false, 
                       results: [[path: 'allure-results']]
            }
        }
    }
}
