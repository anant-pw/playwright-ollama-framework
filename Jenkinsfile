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
                bat '''
                    set TARGET_URLS=https://phet-dev.colorado.edu/html/build-an-atom/0.0.0-3/simple-text-only-test-page.html
                    set BROWSER=chromium
                    python -X utf8 pytest --alluredir=allure-results -v
            '''
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
