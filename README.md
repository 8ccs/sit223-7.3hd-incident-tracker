# Incident Tracker -- SIT223/SIT753 7.3HD Jenkins DevOps Pipeline

A small incident-tracking web app (Flask + SQLite) used as the subject of a
seven-stage Jenkins pipeline: **Build, Test, Code Quality, Security, Deploy,
Release, Monitoring**.

## 1. Project

CRUD incident tracker with:
- REST API (`/api/incidents`) with create/read/update/delete, status and
  severity filtering, free-text search, and a business rule (an incident
  must be `resolved` or `closed` before it can be deleted).
- A small server-rendered dashboard (`/`) with a filter form.
- `/health` (readiness/liveness) and `/metrics` (Prometheus format)
  endpoints.
- Persistent storage in SQLite, one database file per environment.

**Stack:** Python 3.11, Flask, `prometheus-client`, SQLite (stdlib
`sqlite3`), Waitress (production WSGI server for Windows), pytest,
flake8 + pylint + radon (code quality), Bandit + pip-audit (security),
Prometheus + Alertmanager (monitoring), Jenkins (native Windows service,
declarative pipeline).

### Why no Docker

This machine did not have Docker Desktop installed, and installing it
would need admin rights, a large download, and a restart. Rather than
block the whole pipeline on that, the Build stage produces a versioned
**zip artifact** instead of a container image (the brief explicitly
allows "a JAR file, Docker image, or any other artefact"). Deploy and
Release extract that same zip into isolated per-environment folders with
their own venv, port, database file, and process -- the same separation a
container would give, without needing a container runtime. If Docker is
installed later, the Dockerfile-equivalent step would just replace
`scripts/package_artifact.ps1`; nothing else in the pipeline shape would
need to change.

## 2. Repository layout

```
app/                Flask application (factory in app.py, routes in routes.py)
templates/, static/ Dashboard HTML/CSS
tests/unit/          Pure-logic unit tests (validation, SQLite store)
tests/integration/   Flask test-client API tests (incl. failure cases)
scripts/              PowerShell + Python automation used by the Jenkinsfile
monitoring/           Prometheus, Alertmanager, and the local alert-inbox app
config/                Example (non-secret) environment files
Jenkinsfile
requirements.txt       Runtime dependencies (shipped in the artifact)
requirements-dev.txt    + test/quality/security tooling (CI only)
```

## 3. Prerequisites (this machine: Windows 11, PowerShell 5.1 + Git Bash)

Already present and used as-is:
- **Python 3.11** (`python --version`)
- **Git** (`git --version`)
- **Jenkins 2.568.2**, running as a Windows service on `http://localhost:8080`
  (`Get-Service Jenkins`), with security enabled.
- **GitHub CLI** (`gh`), already authenticated.

Installed for this project (see section 5):
- **Prometheus** and **Alertmanager** (native Windows binaries, no admin
  rights needed -- unzipped into `C:\devops-demo\tools`).

Not installed / not used: Docker Desktop, SonarQube. Code quality uses
flake8 + pylint + radon (all pure Python, no server to run) as a
justified equivalent to SonarQube for this project's size -- see the
"Code Quality" section below for why.

## 4. First-time setup

From a fresh clone:

```powershell
git clone <your GitHub repo URL> incident-tracker
cd incident-tracker

python -m venv .venv
.\.venv\Scripts\pip.exe install --disable-pip-version-check -r requirements-dev.txt

# Run the test suite locally
.\.venv\Scripts\pytest.exe tests\unit tests\integration --cov=app --cov-report=term-missing

# Run the app locally (dev server, NOT what Jenkins deploys)
$env:APP_ENV="dev"; $env:PORT="5000"; $env:DB_PATH="data\dev.db"
.\.venv\Scripts\python.exe -m app.app
# then open http://127.0.0.1:5000
```

Everything above only touches the git working copy. Nothing is installed
system-wide by these commands.

## 5. Monitoring stack (Prometheus + Alertmanager + local alert inbox)

These run continuously as **local infrastructure**, independent of any
one Jenkins build (the same way a real Prometheus server would). Jenkins'
Monitoring stage *verifies and exercises* them; it does not start them
from scratch on every run.

```powershell
# One-time download (Windows amd64 binaries, official releases):
New-Item -ItemType Directory -Force -Path C:\devops-demo\tools | Out-Null
Invoke-WebRequest https://github.com/prometheus/prometheus/releases/download/v3.14.0/prometheus-3.14.0.windows-amd64.zip -OutFile C:\devops-demo\tools\prometheus.zip
Invoke-WebRequest https://github.com/prometheus/alertmanager/releases/download/v0.34.1/alertmanager-0.34.1.windows-amd64.zip -OutFile C:\devops-demo\tools\alertmanager.zip
Expand-Archive C:\devops-demo\tools\prometheus.zip -DestinationPath C:\devops-demo\tools -Force
Expand-Archive C:\devops-demo\tools\alertmanager.zip -DestinationPath C:\devops-demo\tools -Force

# Start the local alert inbox (dev stand-in for a real Slack/Teams webhook --
# see "Monitoring" below for how to point this at a real channel instead)
.\.venv\Scripts\pip.exe install flask
Start-Process -FilePath .\.venv\Scripts\python.exe -ArgumentList "monitoring\webhook_receiver.py" -WindowStyle Hidden

# Start Alertmanager
Start-Process -FilePath C:\devops-demo\tools\alertmanager-0.34.1.windows-amd64\alertmanager.exe `
  -ArgumentList "--config.file=$PWD\monitoring\alertmanager.yml" -WindowStyle Hidden

# Start Prometheus (run from the repo so its relative rule_files path resolves)
Start-Process -FilePath C:\devops-demo\tools\prometheus-3.14.0.windows-amd64\prometheus.exe `
  -ArgumentList "--config.file=$PWD\monitoring\prometheus.yml" -WorkingDirectory "$PWD\monitoring" -WindowStyle Hidden
```

Check they are up:
- Prometheus UI: http://localhost:9090 (Status > Targets should show
  `incident-tracker-production` and `incident-tracker-staging`; they read
  `down` until something is deployed to those ports -- see section 6).
- Alertmanager UI: http://localhost:9093
- Local alert inbox: http://localhost:9099/alerts

## 6. Jenkins setup

### 6.1 Plugins

Jenkins already has git, github, github-branch-source, workflow-aggregator
(Pipeline), junit, credentials, and timestamper installed. No extra
plugin is required for this pipeline: coverage/quality/security reports
are archived as workspace artifacts rather than rendered through a
dedicated plugin, to keep the plugin footprint (and thing that can break)
small. If you want in-Jenkins HTML rendering of the coverage/quality
reports, install the **HTML Publisher** plugin (Manage Jenkins > Plugins)
and add an `publishHTML` post step pointing at `reports/test/htmlcov`.

### 6.2 Create the pipeline job

1. Jenkins > New Item > name it `SIT223-7.3HD-IncidentTracker` > **Pipeline** > OK.
2. Build Triggers > check **"Poll SCM"**, schedule `H/5 * * * *`.
   (Why polling and not a webhook: this Jenkins has no public URL, so
   GitHub cannot reach it directly. SCM polling is the practical
   automatic trigger for a local instance; see the comment at the top of
   `Jenkinsfile`.)
3. Pipeline > Definition: **Pipeline script from SCM**.
   - SCM: Git
   - Repository URL: `<your GitHub repo URL>`
   - Branch: `*/main`
   - Script Path: `Jenkinsfile`
4. Save.

### 6.3 Credentials (none hardcoded)

This project has one optional secret: a real team notification webhook
URL for the Monitoring stage (Slack/Teams/Discord incoming webhook). It
defaults to the local alert inbox (`http://localhost:9099/webhook`) if
not set.

To use a real channel:
1. Jenkins > Manage Jenkins > Credentials > (global) > Add Credentials.
2. Kind: **Secret text**. ID: `alert-webhook-url`. Secret: your real
   webhook URL.
3. In `Jenkinsfile`'s Deploy/Release stages, wrap the `deploy.ps1` calls
   with:
   ```groovy
   withCredentials([string(credentialsId: 'alert-webhook-url', variable: 'ALERT_WEBHOOK_URL')]) {
       powershell '''
           & .\\scripts\\deploy.ps1 -Environment production -ZipPath $env:ARTIFACT_ZIP_PATH -AlertWebhookUrl $env:ALERT_WEBHOOK_URL
       '''
   }
   ```
   and update `monitoring/alertmanager.yml`'s `webhook_configs.url` to
   the same real URL.

No secret is ever committed: `config/*.env.example` hold only safe
placeholders, and the real per-environment `current.env` files that
`scripts/deploy.ps1` generates live under `C:\devops-demo\...`, outside
git (see `.gitignore`).

### 6.4 Run it

Build Now. Watch **Stage View** for the seven stages. Console Output
shows every real command. On success:
- Staging: http://localhost:5001
- Production: http://localhost:5000
- Reports: build page > "Artifacts" (`reports/test`, `reports/quality`,
  `reports/security`, `reports/deploy`, `reports/release`,
  `reports/monitoring`, `dist/`).

## 7. Running tests, quality, and security scans directly (outside Jenkins)

```powershell
# Tests + coverage
.\.venv\Scripts\pytest.exe tests\unit tests\integration --cov=app --cov-report=term-missing --cov-fail-under=80

# Code quality
.\.venv\Scripts\flake8.exe app
.\.venv\Scripts\pylint.exe app --rcfile=.pylintrc
.\.venv\Scripts\radon.exe cc app -s
python scripts\quality_gate.py reports\quality   # after generating the JSON/score files, see Jenkinsfile

# Security
.\.venv\Scripts\bandit.exe -r app -f txt
.\.venv\Scripts\pip-audit.exe -r requirements.txt -f columns
python scripts\security_gate.py reports\security
```

## 8. Deploying both environments and demonstrating an incident

```powershell
# Build an artifact by hand (Jenkins normally does this):
.\.venv\Scripts\python.exe -m venv .venv   # if not already created
& .\scripts\package_artifact.ps1 -Version 1.0.0 -GitCommit (git rev-parse --short HEAD) -BuildNumber manual

# Deploy to staging, then production (same artifact, no rebuild):
& .\scripts\deploy.ps1 -Environment staging    -ZipPath (Get-Content dist\artifact-path.txt)
& .\scripts\deploy.ps1 -Environment production -ZipPath (Get-Content dist\artifact-path.txt)

# Smoke test either one:
.\.venv\Scripts\python.exe scripts\smoke_test.py --base-url http://localhost:5001
.\.venv\Scripts\python.exe scripts\smoke_test.py --base-url http://localhost:5000

# Full automated incident-and-recovery check (what the Monitoring stage runs):
.\.venv\Scripts\python.exe scripts\verify_alert_path.py

# Or do it by hand, to narrate live in the demo:
& .\scripts\simulate_incident.ps1   # stops the production process
# watch http://localhost:9090/alerts -- AppDown goes pending -> firing
# watch http://localhost:9099/alerts -- a "firing" entry appears
& .\scripts\recover_incident.ps1    # restarts production on the same version
# watch both pages again -- alert clears, a "resolved" entry appears

# Rollback production to the previous released artifact (no rebuild):
& .\scripts\rollback.ps1 -Environment production
# or, from Jenkins: Build with Parameters > check ROLLBACK_PRODUCTION > Build
```

## 9. Shutdown / restart

```powershell
# Stop the app processes for an environment:
Get-Content C:\devops-demo\staging\app.pid, C:\devops-demo\production\app.pid |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

# Stop monitoring stack: find and stop prometheus.exe, alertmanager.exe,
# and the webhook_receiver.py python process (Task Manager, or
# Get-Process prometheus,alertmanager | Stop-Process).

# To start again, re-run the "Start-Process" commands in section 5, then
# re-deploy staging/production as in section 8 (or just re-run the
# Jenkins job).
```

Data is not lost across restarts: each environment's SQLite file lives
under `C:\devops-demo\<env>\data\incidents.db` and is only touched by
that environment's own process.

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Invoke-RestMethod : Unable to connect` during Deploy | App process failed to start (check `C:\devops-demo\<env>\logs\app.err.log`) | Common cause: port already in use by a leftover process from a previous failed run. `deploy.ps1` already tries to free the port; if it still fails, find and stop the process manually: `Get-NetTCPConnection -LocalPort 5000` then `Stop-Process`. |
| Monitoring stage fails at "preflight" | Prometheus/Alertmanager/webhook inbox not running | Start them (section 5) before running the pipeline; they are long-running infrastructure, not something Jenkins starts. |
| `pytest` can't import `app` | Running pytest from the wrong directory, or `pytest.ini`'s `pythonpath = .` missing | Always run pytest from the repo root; `pytest.ini` already sets `pythonpath = .`. |
| `python app\app.py` fails with `ModuleNotFoundError: No module named 'app.metrics'` | Running the file directly puts `app\` (not the repo root) on `sys.path` | Run `python -m app.app` from the repo root instead (see section 4). |
| Jenkins job stuck "waiting for next available executor" | Another build already running (`disableConcurrentBuilds()`) or agent busy | Wait for the current build, or check Jenkins > Manage Jenkins > Nodes. |
| Quality/Security gate fails unexpectedly | A real new finding, or a tool version drifted | Read `reports/quality/pylint.txt` or `reports/security/bandit.txt` in the build's archived artifacts -- the gate scripts print exactly which check failed and why. |

## 11. Credential setup summary (nothing secret is committed)

| Secret | Where it lives | How it reaches the app |
|---|---|---|
| `ALERT_WEBHOOK_URL` (optional, real team channel) | Jenkins Credentials store, kind "Secret text", id `alert-webhook-url` | Passed to `scripts/deploy.ps1 -AlertWebhookUrl` via `withCredentials`; written into the gitignored `C:\devops-demo\<env>\current.env` at deploy time. |

No database password, API key, or token is required for this project
(SQLite is a local file, GitHub access uses the existing `gh` CLI login,
Jenkins access uses your existing Jenkins account).

## 12. Access checklist (for submission)

The assignment brief requires **both** the Marker and the Unit Chair to
be able to view the codebase, even though the provided answer-sheet
template only mentions the "marking tutor". This repository is public,
which satisfies both by default (no invite needed). If you switch it to
private, add both the Marker's and the Unit Chair's GitHub usernames as
collaborators (Settings > Collaborators) -- this cannot be completed by
an assistant without those usernames, and must be checked off by hand
before submission.
