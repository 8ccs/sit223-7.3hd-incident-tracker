# Demo video script -- SIT223/SIT753 7.3HD

Target length: **9 minutes 10 seconds** (limit: 10:00). Language: simple
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
   Note the build number, e.g. `#12`.
3. **Real Slack channel (optional):** if you have set up your own Slack
   webhook with `scripts\configure_notifications.ps1` before recording
   (see README section 5.1), open that Slack channel in a browser tab
   too, so you can show the real notification arriving alongside the
   local inbox. If you have not set this up, skip that tab -- the local
   inbox is what the automated Jenkins verification always relies on
   either way, so the demo is still fully truthful without Slack.
4. **Close/mute** anything that might pop up a notification during
   recording (email, chat apps).
5. **Browser tabs, in this order** (left to right):
   1. Jenkins job page: `http://localhost:8080/job/SIT223-7.3HD-IncidentTracker/`
   2. GitHub repo: `https://github.com/8ccs/sit223-7.3hd-incident-tracker`
   3. Production app: `http://localhost:5000`
   4. Prometheus: `http://localhost:9090/alerts`
   5. Local alert inbox: `http://localhost:9099/alerts`
   6. (optional) Your real Slack channel, if configured
6. **Terminal window -- open it as Administrator**, not a normal window.
   Right-click PowerShell (or Windows Terminal) and choose "Run as
   administrator", or use `Win+X` > "Terminal (Admin)". This matters:
   Jenkins runs as a Windows service under the SYSTEM account, so the
   production process it deploys is also owned by SYSTEM. Later in this
   script, `simulate_incident.ps1` has to stop that process -- a normal,
   non-elevated PowerShell window gets an "Access is denied" error there
   (this happened during real testing of this project), and an elevated
   window does not. Recording the whole terminal segment as Administrator
   avoids a UAC prompt interrupting the middle of the take.
7. **Set the starting folder to `C:\demo`**, a parent folder, NOT
   `C:\demo\incident-tracker`. Make sure `C:\demo\incident-tracker` does
   **not** already exist -- delete it first if you rehearsed here before
   (`Remove-Item -Recurse -Force C:\demo\incident-tracker`). The clone
   command at 00:25 below must create that folder fresh, on camera, from
   the real GitHub repository -- if the folder already exists, `git
   clone` will fail on camera.
8. **Zoom/readability**: set terminal font to at least 16pt, browser zoom
   to 125%. Use a 1080p recording resolution if possible.
9. **Safe demo data**: this project has no login and no personal data --
   nothing to scrub. Do not have unrelated tabs, files, or notifications
   visible.

Screen recording on Windows: use the built-in **Xbox Game Bar**
(`Win+G` > capture widget > record), or `Win+Alt+R` to start/stop
directly. Record system audio off, microphone on. Do a 10-second test
clip first and check the audio levels before the real take.

---

## 00:00-00:25 -- Introduction

**Show:** Your face/voice only, or the Jenkins job page as a title card.

**Say:**
"Hi, I'm going to demonstrate my SIT223 7.3HD DevOps pipeline. My project
is an incident tracker web app, built with Python and Flask. It has a
REST API, a small dashboard, and SQLite storage. I built a Jenkins
pipeline with all seven required stages: Build, Test, Code Quality,
Security, Deploy, Release, and Monitoring. I'll show the code, the
pipeline running, the app itself, and then a live monitoring alert, from
a real problem to a real recovery."

**Demonstrates:** Overview / context for the whole video.

---

## 00:25-01:10 -- Clone the repository and show key files

**Show:** Terminal (already running as Administrator, starting folder
`C:\demo`).

**Type:**
```powershell
cd C:\demo
git clone https://github.com/8ccs/sit223-7.3hd-incident-tracker.git
cd incident-tracker
dir
```

**Say:**
"This is the real GitHub repository, cloned fresh right now. The app
code is in the `app` folder, tests are in `tests`, and all the pipeline
automation scripts are in `scripts`. The `Jenkinsfile` here at the root
is the actual pipeline definition Jenkins runs -- it's not a script I run
by hand, Jenkins loads it directly from this repository."

**Type:**
```powershell
notepad Jenkinsfile
```
(scroll briefly to the stage names, close it)

**Demonstrates:** Repository clone + Jenkinsfile committed to source
control (brief requirement: "how to clone the repository").

---

## 01:10-01:50 -- Jenkins pipeline configuration

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

## 01:50-02:30 -- Trigger the pipeline, Build stage

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

## 02:30-03:10 -- Test stage

**Show:** Jenkins Test stage console output, then the build's "Test
Result" page.

**Say:**
"Next is Test. This runs 78 unit and integration tests with pytest --
unit tests check the validation rules, the database layer, and the
security and quality gate scripts in isolation, integration tests drive
the real Flask API, including failure cases like an invalid severity
value, or trying to delete an incident that's still open. Coverage is
measured and the build fails if it drops below 80 percent -- right now
it's at 98. Jenkins publishes the results here through the JUnit plugin,
so I can see pass/fail per test, not just a console log."

**Demonstrates:** Test stage -- unit + integration, pass/fail gate,
published results (rubric: "structured with clear pass/fail gating").

---

## 03:10-03:50 -- Code Quality stage

**Show:** Jenkins Code Quality stage console output + archived
`reports/quality/pylint.txt`.

**Say:**
"Code Quality runs flake8, pylint, and radon against the app code. I set
a quality gate: pylint must score at least 8 out of 10, and no function
can have a cyclomatic complexity worse than rank C. This actually caught
two real problems while I was building this: a variable used before it
was set in one code path, and one function that was too complex. I fixed
both -- the complex function is now split into a Flask Blueprint, and
pylint's score went from 9.65 up to 9.96 out of 10. I also made this
gate fail if a scan tool errors out or produces an empty report, instead
of quietly treating that as a clean pass -- I found that bug myself
while reviewing this pipeline, and it applies to both quality and
security scanning."

**Demonstrates:** Code Quality -- real tool, explained thresholds, real
findings and fixes, honest gate logic (rubric: "configured quality gates
with explained metrics").

---

## 03:50-04:35 -- Security stage

**Show:** Jenkins Security stage console output + `reports/security/bandit.txt`.

**Say:**
"Security runs Bandit, which scans the code itself, and pip-audit, which
checks my dependencies against known CVEs. pip-audit found zero
vulnerabilities in my runtime dependencies. Bandit found a real issue
during development: the app was binding to all network interfaces, which
is unnecessary here since everything runs on one machine -- I fixed
that. It also flagged dynamic SQL column names as a possible injection
risk. I fixed one case completely by using fixed queries, and for the
other, which genuinely needs a dynamic column list for partial updates,
I added an allow-list check in the code -- only a fixed set of column
names can ever be built into the query, values are always sent as
parameters, never concatenated -- and a documented suppression, rather
than just switching the rule off. This stage also fails the whole build
if a scan doesn't actually finish -- a crashed scanner or an empty
report used to be able to pass silently, and I closed that gap. I'm not
using Docker, so there's no container image to scan here -- that's
explained in the README."

**Demonstrates:** Security -- real scanners, real findings, explained
severity and fixes, explicit and honest gate (rubric: "vulnerabilities
categorized and partially addressed" / "proactive security handling").

---

## 04:35-05:15 -- Deploy stage (staging)

**Show:** Jenkins Deploy stage console output, then browser tab ->
`http://localhost:5001`.

**Say:**
"Deploy sends the exact same artifact to a staging environment, on port
5001, with its own database file and its own Python process, completely
separate from production. The script waits for the health check to
return OK before continuing, then runs five smoke tests against the real
running app -- not a test client, actual HTTP requests. Here's staging
running live."

**Click:** the staging dashboard briefly.

**Demonstrates:** Deploy -- isolated staging environment, readiness
check, staging smoke tests (rubric: "fully automated deployment to
reliable test infra").

---

## 05:15-06:00 -- Release stage (production)

**Show:** Jenkins Release stage console output, then
`http://localhost:5000`.

**Say:**
"Release promotes that same artifact -- not a rebuild -- to production,
on port 5000. It runs the same health check, then records the released
version to a file so I always know what's live, and only after that
health check passes, so a failed deploy never overwrites a good release
record. There's also a rollback script that redeploys the previous
version with no rebuild, wired into Jenkins as a checkbox parameter. I
tested this directly: deploy one version, release a second, simulate an
incident and recover -- which restarts the same version currently
live -- then roll back, and confirm the app is back on the first
version. On a brand-new environment there's nothing to roll back to yet
-- that's a one-time limitation I explain in the README. Here's
production, running the version I just built."

**Click:** the production dashboard, show the version footer if visible,
or `/health` in a new tab showing the version/commit fields.

**Demonstrates:** Release -- same artifact promoted, versioned,
verified rollback mechanism (rubric: "tagged, versioned, automated
release" / "rollback support").

---

## 06:00-06:45 -- The deployed app itself: the REST API

**Show:** Terminal, then the production dashboard tab
(`http://localhost:5000`).

**Say:**
"The dashboard here only lists and filters incidents -- creating,
updating, and deleting one goes through the REST API, which is what the
Test stage actually exercises. I'll do that live now."

**Type:**
```powershell
$incident = Invoke-RestMethod -Method Post `
  -Uri http://localhost:5000/api/incidents `
  -ContentType "application/json" `
  -Body '{"title":"Demo: payment webhook timeout","description":"Created live for the SIT223 video.","severity":"high"}'
$incident
```

**Say:** "That created a new open incident with severity high."
**Switch to the dashboard tab, refresh (Ctrl+F5):** "And here it is on
the dashboard."

**Type:**
```powershell
Invoke-RestMethod -Method Put `
  -Uri "http://localhost:5000/api/incidents/$($incident.id)" `
  -ContentType "application/json" `
  -Body '{"status":"resolved"}'
```

**Say:** "That's a partial update through the same API -- I only sent
the status field, nothing else changes." **Switch to dashboard, refresh:**
"Now it shows as resolved."

**Type:**
```powershell
Invoke-RestMethod -Method Delete `
  -Uri "http://localhost:5000/api/incidents/$($incident.id)"
```

**Say:** "And deleting it. The API actually blocks deleting an incident
unless it's resolved or closed first -- that business rule is one of the
78 tests from the Test stage." **Switch to dashboard, refresh:** "Gone."

**Demonstrates:** The deployed application's real functionality (CRUD,
validation, business rules), not just a pipeline that ends in a blank
page.

---

## 06:45-08:15 -- Monitoring: live metrics, incident, and recovery

**Show:** Prometheus `/targets`, then the terminal, then Prometheus
`/alerts`, then the local alert inbox tab (and the Slack tab, if you
configured it).

**Say:**
"For Monitoring, Prometheus scrapes live metrics from production every
five seconds. I have three alert rules: the app going down, a high error
rate, and high latency. Now I'll actually break production, on purpose,
to prove the whole alert path works -- not just that it's configured."

**Type:**
```powershell
.\scripts\simulate_incident.ps1
```

**Say (while watching Prometheus /alerts):**
"That stopped the production process -- this needed the Administrator
terminal, because Jenkins deployed it under the SYSTEM account.
Prometheus will mark the target down on its next scrape... there it is,
pending, and now firing."

**Switch tab to the alert inbox (and Slack, if configured):**
"And here's the notification. My alerting is wired to two destinations
at once: this local inbox, which is what my automated Jenkins
verification always checks, and a real Slack channel through
Alertmanager's own Slack integration [-- here it is arriving in Slack
too, if you have this configured]. I chose a proper Slack receiver
instead of just posting a webhook URL into a generic handler, because
that's what actually validates the message format Slack expects."

**Type:**
```powershell
.\scripts\recover_incident.ps1
```

**Say (watching both tabs again):**
"That restarts production on the exact same version, no rebuild. Give it
a few seconds... the target is back up, the alert clears in Prometheus,
and the inbox receives a resolved notification. My Jenkins pipeline
actually automates this entire check on every run, using a script called
verify_alert_path.py. It always attempts recovery, even if the alert
check itself fails partway through, so a broken verification can never
leave production down -- and it still fails the build if verification
itself failed, even though recovery succeeded. So I don't just configure
alerting, I prove it fires and recovers every single time."

**Demonstrates:** Monitoring -- live metrics, real alert rules, full
verified path: issue, firing, notification, recovery, resolved, correct
real-channel integration, guaranteed recovery (rubric Top HD: "fully
integrated system with live metrics, meaningful alert rules, and
incident simulation").

---

## 08:15-08:50 -- Review: stages, evidence, repository, answer sheet

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

## 08:50-09:10 -- One real challenge, and closing

**Show:** Your face, or the `app/metrics.py` file briefly.

**Say:**
"One real problem I hit while building this: production kept
disappearing a few seconds after Jenkins said the build succeeded. It
turned out Jenkins was killing every process a build leaves running once
that build finishes, using something called a Windows Job Object. I
fixed it by launching the app through Windows Management Instrumentation
instead, which starts it completely outside Jenkins' process tree, so it
survives. That's the kind of real integration bug you only find by
actually running the full pipeline end to end and checking afterwards,
not just watching it print 'Finished: SUCCESS'. Thanks for watching."

**Demonstrates:** Reflective technical insight (rubric Top HD: "deep
insight and fluent narration").

---

## Troubleshooting during a live recording

| Problem | What to do |
|---|---|
| A stage is slow (pip install, first-time venv) | Don't wait on camera. Cut here and resume with "as you can see, the pipeline has moved on to..." pointing at an already-finished stage from your unrecorded warm-up run, and say clearly: "I ran this once before recording to warm the cache; here is that completed run" if you use pre-recorded evidence for a slow step. |
| `simulate_incident.ps1` still says "Access is denied" | The terminal is not actually elevated. Close it, right-click PowerShell/Windows Terminal, "Run as administrator", and restart the take from 00:25 (or from the last section, if you're recording in segments). |
| Port already in use / deploy fails | Stop before recording: `Get-NetTCPConnection -LocalPort 5000,5001 | Stop-Process -Id {$_.OwningProcess} -Force` (run this from the elevated terminal too). |
| Alert doesn't fire within the expected ~20s | Wait up to 60s on camera while narrating what should happen; if it still hasn't fired, cut to the warm-up run's Prometheus/inbox screenshots and say so honestly. |
| Browser shows a stale cached page | Hard refresh (Ctrl+F5) before switching tabs on camera -- this is required after every API call in the 06:00-06:45 section, not optional. |
| Recording runs long | Trim the Code Quality or Security stage narration first (03:10-04:35 range) -- keep Build/Test/Deploy/Release/Monitoring/API-demo intact, those carry the most rubric weight. |

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
