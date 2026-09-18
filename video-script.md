# Demo video script -- SIT223/SIT753 7.3HD

Target length: **9 minutes 15 seconds** (limit: 10:00). Language: simple
B2 English, short sentences, spoken naturally -- read this as a guide, not
word-for-word if that feels stiff, but keep the content and order.

This script assumes the pipeline has already been run at least once
successfully before recording (see "Before recording" below), so the
Jenkins job history has a real, complete, green build to show, and the
monitoring stack is already warm. All commands below are the real
commands used in this project; adjust the Jenkins job name if you named
it differently.

---

## Before recording -- checklist

Run through this the day of recording, in order:

1. **Start the monitoring stack** (Prometheus, Alertmanager, local alert
   inbox) -- see README.md section 5. Confirm:
   - http://localhost:9090/targets -- both `incident-tracker-production`
     and `incident-tracker-staging` show `UP` (they will only show up if
     something is already deployed; if this is a completely fresh
     machine, run the Jenkins job once, unrecorded, first so these exist).
   - http://localhost:9093 loads.
   - http://localhost:9099/alerts loads.
2. **Run the Jenkins job once, unrecorded**, so caches are warm (pip
   packages, venvs already created) and you know it currently passes.
   Note the build number, e.g. `#7`.
3. **Close/mute** anything that might pop up a notification during
   recording (email, chat apps).
4. **Browser tabs, in this order** (left to right):
   1. Jenkins job page: `http://localhost:8080/job/SIT223-7.3HD-IncidentTracker/`
   2. GitHub repo: `https://github.com/8ccs/sit223-7.3hd-incident-tracker`
   3. Production app: `http://localhost:5000`
   4. Prometheus: `http://localhost:9090/alerts`
   5. Local alert inbox: `http://localhost:9099/alerts`
5. **Terminal window**: PowerShell, working directory set to a *fresh
   clone* of the repo (not your existing working copy) at
   `C:\demo\incident-tracker` -- see step 00:30 below for why.
6. **Zoom/readability**: set terminal font to at least 16pt, browser zoom
   to 125%. Use a 1080p recording resolution if possible.
7. **Safe demo data**: this project has no login and no personal data --
   nothing to scrub. Do not have unrelated tabs, files, or notifications
   visible.

Screen recording on Windows: use the built-in **Xbox Game Bar**
(`Win+G` > capture widget > record), or `Win+Alt+R` to start/stop
directly. Record system audio off, microphone on. Do a 10-second test
clip first and check the audio levels before the real take.

---

## 00:00-00:30 -- Introduction

**Show:** Your face/voice only, or the Jenkins job page as a title card.

**Say:**
"Hi, I'm going to demonstrate my SIT223 7.3HD DevOps pipeline. My project
is an incident tracker web app, built with Python and Flask. It has a
REST API, a small dashboard, and SQLite storage. I built a Jenkins
pipeline with all seven required stages: Build, Test, Code Quality,
Security, Deploy, Release, and Monitoring. I'll show the code, the
pipeline running, and then a live monitoring alert, from a real problem
to a real recovery."

**Demonstrates:** Overview / context for the whole video.

---

## 00:30-01:15 -- Clone the repository and show key files

**Show:** Terminal.

**Type:**
```powershell
git clone https://github.com/8ccs/sit223-7.3hd-incident-tracker.git C:\demo\incident-tracker
cd C:\demo\incident-tracker
dir
```

**Say:**
"This is the real GitHub repository, cloned fresh. The app code is in
the `app` folder, tests are in `tests`, and all the pipeline automation
scripts are in `scripts`. The `Jenkinsfile` here at the root is the
actual pipeline definition Jenkins runs -- it's not a script I run by
hand, Jenkins loads it directly from this repository."

**Type:**
```powershell
notepad Jenkinsfile
```
(scroll briefly to the stage names, close it)

**Demonstrates:** Repository clone + Jenkinsfile committed to source
control (brief requirement: "how to clone the repository").

---

## 01:15-02:00 -- Jenkins pipeline configuration

**Show:** Jenkins job page (Configure screen).

**Say:**
"This is the Jenkins job. It's a Pipeline job, and its definition is set
to 'Pipeline script from SCM' -- Jenkins pulls the Jenkinsfile straight
from the GitHub repository I just cloned, on every run. I also set 'Poll
SCM' as the trigger, checking every five minutes for new commits. I used
polling instead of a GitHub webhook because this Jenkins instance runs
on my own machine with no public URL for GitHub to reach -- that's
explained in the README and at the top of the Jenkinsfile."

**Demonstrates:** Pipeline-from-SCM setup, automatic trigger + why
(Build stage requirement: "automatic source-change trigger").

---

## 02:00-02:40 -- Trigger the pipeline, Build stage

**Show:** Jenkins > Build Now > Stage View.

**Say:**
"I'll start a build now. ... The first stage after checkout is Build. It
creates a Python virtual environment, then runs a PowerShell script that
packages the app into a versioned zip file -- the version includes the
Git commit hash and this Jenkins build number, so I always know exactly
what code is running. I don't have Docker installed on this machine, so
I'm using a zip artifact instead of a container image -- the same
artifact is what Deploy and Release both use later, unchanged."

**Click:** into the Build stage log briefly, point at the version string
in the console output (e.g. `incident-tracker-1.0.0+build.12.a0f1f0a.zip`).

**Demonstrates:** Build stage -- real artifact, versioned by commit +
build number.

---

## 02:40-03:20 -- Test stage

**Show:** Jenkins Test stage console output, then the build's "Test
Result" page.

**Say:**
"Next is Test. This runs 48 unit and integration tests with pytest --
unit tests check the validation rules and the database layer in
isolation, integration tests drive the real Flask API, including failure
cases like an invalid severity value, or trying to delete an incident
that's still open. Coverage is measured and the build fails if it drops
below 80 percent -- right now it's at 98. Jenkins publishes the results
here through the JUnit plugin, so I can see pass/fail per test, not just
a console log."

**Demonstrates:** Test stage -- unit + integration, pass/fail gate,
published results (rubric: "structured with clear pass/fail gating").

---

## 03:20-04:00 -- Code Quality stage

**Show:** Jenkins Code Quality stage console output + archived
`reports/quality/pylint.txt`.

**Say:**
"Code Quality runs flake8, pylint, and radon against the app code. I set
a quality gate: pylint must score at least 8 out of 10, and no function
can have a cyclomatic complexity worse than rank C. This actually caught
two real problems while I was building this: a variable used before it
was set in one code path, and one function that was too complex. I fixed
both -- the complex function is now split into a Flask Blueprint, and
pylint's score went from 9.65 up to 9.96 out of 10."

**Demonstrates:** Code Quality -- real tool, explained thresholds, real
findings and fixes (rubric: "configured quality gates with explained
metrics").

---

## 04:00-04:40 -- Security stage

**Show:** Jenkins Security stage console output + `reports/security/bandit.txt`.

**Say:**
"Security runs Bandit, which scans the code itself, and pip-audit, which
checks my dependencies against known CVEs. pip-audit found zero
vulnerabilities in my nine runtime dependencies. Bandit found a real
issue during development: the app was binding to all network interfaces,
which is unnecessary here since everything runs on one machine -- I
fixed that. It also flagged dynamic SQL column names as a possible
injection risk. I fixed one case completely by using fixed queries, and
for the other, which genuinely needs a dynamic column list for partial
updates, I added an allow-list check in the code and a documented
suppression, rather than just switching the rule off. I'm not using
Docker, so there's no container image to scan here -- that's explained
in the README."

**Demonstrates:** Security -- real scanners, real findings, explained
severity and fixes, explicit gate (rubric: "vulnerabilities categorized
and partially addressed" / "proactive security handling").

---

## 04:40-05:25 -- Deploy stage (staging)

**Show:** Jenkins Deploy stage console output, then browser tab ->
`http://localhost:5001`.

**Say:**
"Deploy sends the exact same artifact to a staging environment, on port
5001, with its own database file and its own Python process, completely
separate from production. The script waits for the health check to
return OK before continuing, then runs five smoke tests against the real
running app -- not a test client, actual HTTP requests. Here's staging
running live."

**Click:** the staging dashboard, create one demo incident live if time
allows.

**Demonstrates:** Deploy -- isolated staging environment, readiness
check, staging smoke tests (rubric: "fully automated deployment to
reliable test infra").

---

## 05:25-06:15 -- Release stage (production)

**Show:** Jenkins Release stage console output, then
`http://localhost:5000`.

**Say:**
"Release promotes that same artifact -- not a rebuild -- to production,
on port 5000. It runs the same health check, then records the released
version to a file so I always know what's live. There's also a rollback
script that redeploys the previous version with no rebuild, wired into
Jenkins as a checkbox parameter, in case a release needs to be undone. On
a brand-new environment there's nothing to roll back to yet -- that's a
one-time limitation I explain in the README. Here's production, running
the same version I just built."

**Click:** the production dashboard, show the version footer if visible,
or `/health` in a new tab showing the version/commit fields.

**Demonstrates:** Release -- same artifact promoted, versioned,
rollback mechanism (rubric: "tagged, versioned, automated release" /
"rollback support").

---

## 06:15-07:45 -- Monitoring: live metrics, incident, and recovery

**Show:** Prometheus `/targets`, then a terminal, then Prometheus
`/alerts`, then the local alert inbox tab.

**Say:**
"For Monitoring, Prometheus scrapes live metrics from production every
five seconds. I have three alert rules: the app going down, a high error
rate, and high latency. Now I'll actually break production, on purpose,
to prove the whole alert path works -- not just that it's configured."

**Type:**
```powershell
cd C:\demo\incident-tracker
.\scripts\simulate_incident.ps1
```

**Say (while watching Prometheus /alerts):**
"That stopped the production process. Prometheus will mark the target
down on its next scrape... there it is, pending, and now firing."

**Switch tab to the alert inbox:**
"And here's the notification -- this local inbox stands in for a real
Slack or Teams webhook during development, which I explain in the
README. It just received the firing alert."

**Type:**
```powershell
.\scripts\recover_incident.ps1
```

**Say (watching both tabs again):**
"That restarts production on the exact same version, no rebuild. Give it
a few seconds... the target is back up, the alert clears in Prometheus,
and the inbox receives a resolved notification. My Jenkins pipeline
actually automates this entire check on every run, using a script called
verify_alert_path.py, so I don't just configure alerting, I prove it
fires and recovers every single time."

**Demonstrates:** Monitoring -- live metrics, real alert rules, full
verified path: issue, firing, notification, recovery, resolved (rubric
Top HD: "fully integrated system with live metrics, meaningful alert
rules, and incident simulation").

---

## 07:45-08:45 -- Review: stages, evidence, repository, answer sheet

**Show:** Jenkins Stage View (all seven green), then the build's
Artifacts list, then the GitHub repo tab, then the answer-sheet PDF.

**Say:**
"So that's all seven stages, passing in this run: Build, Test, Code
Quality, Security, Deploy, Release, and Monitoring. Every stage archives
its real reports as Jenkins build artifacts -- test results, coverage,
lint output, security scan output, deploy and release logs, and the
monitoring verification record -- so none of this is just console text
that disappears. The Jenkinsfile and all of this code are in the public
GitHub repository, so both my marker and the unit chair can view it
without needing an invite. And this is my completed answer sheet, with
the repository link, the video link, and a screenshot of this same
pipeline."

**Demonstrates:** Overall pipeline completeness + report/evidence
quality (rubric: "Report Quality" / "Pipeline Completeness").

---

## 08:45-09:15 -- One real challenge, and closing

**Show:** Your face, or the `app/metrics.py` file briefly.

**Say:**
"One real problem I hit while building this: my automated monitoring
check kept hanging after a successful recovery. It turned out that when
PowerShell starts the production server as a background process, that
process can inherit and keep open file handles from the script that
launched it, on Windows -- so Python's subprocess call was waiting
forever for a pipe to close that never would. I fixed it by writing that
output to files instead of pipes, and adding an explicit timeout as a
safety net. That's the kind of real integration issue you only find by
actually running the full pipeline end to end, not just writing it.
Thanks for watching."

**Demonstrates:** Reflective technical insight (rubric Top HD: "deep
insight and fluent narration").

---

## Troubleshooting during a live recording

| Problem | What to do |
|---|---|
| A stage is slow (pip install, first-time venv) | Don't wait on camera. Cut here and resume with "as you can see, the pipeline has moved on to..." pointing at an already-finished stage from your unrecorded warm-up run, and say clearly: "I ran this once before recording to warm the cache; here is that completed run" if you use pre-recorded evidence for a slow step. |
| Port already in use / deploy fails | Stop before recording: `Get-NetTCPConnection -LocalPort 5000,5001 | Stop-Process -Id {$_.OwningProcess} -Force` |
| Alert doesn't fire within the expected ~20s | Wait up to 60s on camera while narrating what should happen; if it still hasn't fired, cut to the warm-up run's Prometheus/inbox screenshots and say so honestly. |
| Browser shows a stale cached page | Hard refresh (Ctrl+F5) before switching tabs on camera. |
| Recording runs long | Trim the Code Quality or Security stage narration first (04:00-04:40 range) -- keep Build/Test/Deploy/Release/Monitoring intact, those carry the most rubric weight. |

## After recording

1. Check the exported file's duration is under 10:00 and that audio is
   audible throughout (play back at least the first, middle, and last
   30 seconds).
2. Upload it (e.g. YouTube unlisted, or your institution's video
   platform).
3. Open the link in a private/incognito window to confirm it plays
   without your personal login -- this is what "verify assessor access"
   means in practice.
4. Replace the `[PENDING - VIDEO LINK]` marker in the answer sheet with
   the real link.
5. Re-export the answer sheet to PDF and re-check it (see the PDF
   checklist in the handover notes).
