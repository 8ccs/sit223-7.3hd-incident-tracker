// SIT223/SIT753 7.3HD -- DevOps Pipeline with Jenkins
//
// Seven required stages: Build, Test, Code Quality, Security, Deploy,
// Release, Monitoring. "Checkout" is setup only and is not one of the
// seven. No Docker is installed on this agent, so the artifact is a
// versioned zip rather than a container image; see README.md for the
// reasoning. All later stages read the same artifact -- Release never
// rebuilds the application.
//
// Reference docs used while writing this file:
//   https://www.jenkins.io/doc/book/pipeline/jenkinsfile/
//   https://www.jenkins.io/doc/book/pipeline/docker/ (evaluated, not used -- see README)
//   https://prometheus.io/docs/alerting/latest/overview/

pipeline {
    agent any

    parameters {
        booleanParam(
            name: 'ROLLBACK_PRODUCTION',
            defaultValue: false,
            description: 'When checked, this run rolls production back to the previous released artifact instead of building/deploying/releasing the current commit. Demonstrates the rollback mechanism without rebuilding anything.'
        )
    }

    options {
        timestamps()
        timeout(time: 45, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    // Automatic source-change trigger. This Jenkins instance runs on a
    // personal machine with no public URL, so a GitHub push webhook
    // cannot reach it without an extra tunnel (ngrok/smee), which is
    // unnecessary complexity for a local demo. SCM polling every 5
    // minutes is the practical automatic trigger for this environment;
    // the github-branch-source plugin is already installed so a webhook
    // can be switched on later with no pipeline changes if Jenkins is
    // ever exposed on a public URL.
    triggers {
        pollSCM('H/5 * * * *')
    }

    environment {
        APP_BASE_VERSION = '1.0.0'
        VENV             = "${WORKSPACE}\\.venv"
        ARTIFACT_STORE   = 'C:\\devops-demo\\artifacts'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_COMMIT_SHORT = powershell(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                }
                echo "Commit ${env.GIT_COMMIT_SHORT} · Jenkins build #${env.BUILD_NUMBER} · job ${env.JOB_NAME}"
            }
        }

        // ---------------------------------------------------------------
        // 1) BUILD -- produce a versioned, deployable artifact
        // ---------------------------------------------------------------
        stage('Build') {
            when { expression { !params.ROLLBACK_PRODUCTION } }
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"
                    if (-not (Test-Path $env:VENV)) {
                        python -m venv $env:VENV
                    }
                    & "$env:VENV\\Scripts\\pip.exe" install --quiet --disable-pip-version-check -r requirements-dev.txt

                    & .\\scripts\\package_artifact.ps1 -Version $env:APP_BASE_VERSION -GitCommit $env:GIT_COMMIT_SHORT -BuildNumber $env:BUILD_NUMBER
                '''
                script {
                    env.ARTIFACT_ZIP_NAME = readFile('dist/artifact-name.txt').trim()
                    env.ARTIFACT_ZIP_PATH = readFile('dist/artifact-path.txt').trim()
                    env.FULL_VERSION      = readFile('dist/full-version.txt').trim()
                }
                echo "Built artifact ${env.ARTIFACT_ZIP_NAME} -> version ${env.FULL_VERSION}"
                archiveArtifacts artifacts: 'dist/*.zip, dist/*.json, dist/*.txt', fingerprint: true
            }
        }

        // ---------------------------------------------------------------
        // 2) TEST -- unit + integration tests, coverage, pass/fail gate
        // ---------------------------------------------------------------
        stage('Test') {
            when { expression { !params.ROLLBACK_PRODUCTION } }
            steps {
                powershell '''
                    New-Item -ItemType Directory -Force -Path reports\\test | Out-Null
                    & "$env:VENV\\Scripts\\pytest.exe" tests\\unit tests\\integration `
                        --junitxml=reports\\test\\junit.xml `
                        --cov=app --cov-report=xml:reports\\test\\coverage.xml `
                        --cov-report=html:reports\\test\\htmlcov `
                        --cov-report=term-missing `
                        --cov-fail-under=80
                    exit $LASTEXITCODE
                '''
            }
            post {
                always {
                    junit testResults: 'reports/test/junit.xml', allowEmptyResults: true
                    archiveArtifacts artifacts: 'reports/test/**', allowEmptyArchive: true
                }
            }
        }

        // ---------------------------------------------------------------
        // 3) CODE QUALITY -- maintainability, style, complexity, duplication
        //    (separate from Security; see .flake8 / .pylintrc for gates)
        // ---------------------------------------------------------------
        stage('Code Quality') {
            when { expression { !params.ROLLBACK_PRODUCTION } }
            steps {
                powershell '''
                    New-Item -ItemType Directory -Force -Path reports\\quality | Out-Null

                    & "$env:VENV\\Scripts\\flake8.exe" app --format=default | Out-File reports\\quality\\flake8.txt -Encoding utf8
                    $global:LASTEXITCODE = 0

                    & "$env:VENV\\Scripts\\pylint.exe" app --rcfile=.pylintrc | Out-File reports\\quality\\pylint.txt -Encoding utf8
                    $global:LASTEXITCODE = 0
                    & "$env:VENV\\Scripts\\pylint.exe" app --rcfile=.pylintrc --output-format=json | Out-File reports\\quality\\pylint.json -Encoding utf8
                    $global:LASTEXITCODE = 0

                    $scoreLine = Select-String -Path reports\\quality\\pylint.txt -Pattern "rated at (-?\\d+\\.\\d+)/10"
                    if ($scoreLine) { $score = $scoreLine.Matches[0].Groups[1].Value } else { $score = "0.0" }
                    Set-Content -Path reports\\quality\\pylint-score.txt -Value $score -NoNewline

                    & "$env:VENV\\Scripts\\radon.exe" cc app -s -j | Out-File reports\\quality\\radon-cc.json -Encoding utf8
                    $global:LASTEXITCODE = 0
                    & "$env:VENV\\Scripts\\radon.exe" mi app -s | Out-File reports\\quality\\radon-mi.txt -Encoding utf8
                    $global:LASTEXITCODE = 0

                    & "$env:VENV\\Scripts\\python.exe" scripts\\quality_gate.py reports\\quality
                    exit $LASTEXITCODE
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/quality/**', allowEmptyArchive: true
                }
            }
        }

        // ---------------------------------------------------------------
        // 4) SECURITY -- SAST (Bandit) + dependency scan (pip-audit)
        //    No container image is produced (Docker-free stack), so
        //    there is no image to scan with Trivy; see README.md.
        // ---------------------------------------------------------------
        stage('Security') {
            when { expression { !params.ROLLBACK_PRODUCTION } }
            steps {
                powershell '''
                    New-Item -ItemType Directory -Force -Path reports\\security | Out-Null

                    & "$env:VENV\\Scripts\\bandit.exe" -r app -f json -o reports\\security\\bandit.json
                    $global:LASTEXITCODE = 0
                    & "$env:VENV\\Scripts\\bandit.exe" -r app -f txt -o reports\\security\\bandit.txt
                    $global:LASTEXITCODE = 0

                    & "$env:VENV\\Scripts\\pip-audit.exe" -r requirements.txt -f json -o reports\\security\\pip-audit.json
                    $global:LASTEXITCODE = 0
                    & "$env:VENV\\Scripts\\pip-audit.exe" -r requirements.txt -f columns | Out-File reports\\security\\pip-audit.txt -Encoding utf8
                    $global:LASTEXITCODE = 0

                    & "$env:VENV\\Scripts\\python.exe" scripts\\security_gate.py reports\\security
                    exit $LASTEXITCODE
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/security/**', allowEmptyArchive: true
                }
            }
        }

        // ---------------------------------------------------------------
        // 5) DEPLOY -- staging environment, readiness check, smoke tests
        // ---------------------------------------------------------------
        stage('Deploy') {
            when { expression { !params.ROLLBACK_PRODUCTION } }
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"
                    & .\\scripts\\deploy.ps1 -Environment staging -ZipPath $env:ARTIFACT_ZIP_PATH
                '''
                powershell '''
                    & "$env:VENV\\Scripts\\python.exe" scripts\\smoke_test.py --base-url http://localhost:5001 --report reports\\deploy\\staging-smoke.json
                    exit $LASTEXITCODE
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/deploy/**', allowEmptyArchive: true
                }
            }
        }

        // ---------------------------------------------------------------
        // 6) RELEASE -- promote the SAME artifact to production
        // ---------------------------------------------------------------
        stage('Release') {
            steps {
                script {
                    if (params.ROLLBACK_PRODUCTION) {
                        powershell '''
                            $ErrorActionPreference = "Stop"
                            & .\\scripts\\rollback.ps1 -Environment production
                        '''
                    } else {
                        powershell '''
                            $ErrorActionPreference = "Stop"
                            & .\\scripts\\deploy.ps1 -Environment production -ZipPath $env:ARTIFACT_ZIP_PATH
                        '''
                    }
                }
                powershell '''
                    New-Item -ItemType Directory -Force -Path reports\\release | Out-Null
                    & "$env:VENV\\Scripts\\python.exe" scripts\\smoke_test.py --base-url http://localhost:5000 --report reports\\release\\production-health.json
                    exit $LASTEXITCODE
                '''
                powershell '''
                    Copy-Item C:\\devops-demo\\production\\current_version.txt reports\\release\\released-version.txt -Force
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/release/**', allowEmptyArchive: true
                }
            }
        }

        // ---------------------------------------------------------------
        // 7) MONITORING -- live metrics + automated alert-path verification
        // ---------------------------------------------------------------
        stage('Monitoring') {
            when { expression { !params.ROLLBACK_PRODUCTION } }
            steps {
                powershell '''
                    New-Item -ItemType Directory -Force -Path reports\\monitoring | Out-Null
                    & "$env:VENV\\Scripts\\python.exe" scripts\\verify_alert_path.py
                    exit $LASTEXITCODE
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/monitoring/**', allowEmptyArchive: true
                }
            }
        }
    }

    post {
        always {
            echo "Pipeline finished for commit ${env.GIT_COMMIT_SHORT ?: 'unknown'} (build #${env.BUILD_NUMBER})."
        }
        success {
            echo "All required stages passed. Version ${env.FULL_VERSION ?: '(rollback run)'} is live in production."
        }
        failure {
            echo 'Pipeline failed -- see the failed stage above. Production was only updated if Release itself completed; check reports/release for the last known-good version and use scripts/rollback.ps1 if needed.'
        }
    }
}
