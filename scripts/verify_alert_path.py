#!/usr/bin/env python
"""Monitoring stage: automated, end-to-end verification of the alert path.

This does not just check that Prometheus/Alertmanager are configured; it
actually breaks the production app, waits for Prometheus to notice, waits
for the AppDown alert rule to fire, confirms the local webhook inbox
received a "firing" notification, restores the app, and confirms both
Prometheus and the inbox see the alert as resolved.

Every step is verified over HTTP against the real running services
(Prometheus :9090, Alertmanager :9093, webhook inbox :9099). If any step
does not happen within its timeout, this script exits non-zero and the
Monitoring stage fails -- a configured-but-never-fired alert is treated
as a failure, not a pass.

Usage: python scripts/verify_alert_path.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PS1_LOG_DIR = Path("reports/monitoring/ps1-logs")

PROM_URL = "http://localhost:9090"
ALERTMANAGER_URL = "http://localhost:9093"
INBOX_URL = "http://localhost:9099"
PROD_METRICS_URL = "http://localhost:5000/metrics"
ALERT_NAME = "AppDown"

SCRIPTS_DIR = Path(__file__).parent
REPORT_PATH = Path("reports/monitoring/alert-path-verification.json")

timeline: dict[str, str] = {}


def log(msg: str) -> None:
    print(f"[verify-alert-path] {msg}", flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_ps1(name: str, timeout_s: int = 90) -> None:
    """Run a PowerShell script and wait for it to finish.

    Output is redirected to FILES rather than captured with pipes,
    because deploy.ps1 launches a detached waitress process with
    Start-Process; on Windows that grandchild can inherit and hold open
    the parent's stdout/stderr PIPE handles even after the parent script
    exits, which makes subprocess.run(capture_output=True) hang forever
    waiting for end-of-pipe that never comes.

    The same inheritance means the detached waitress process can also
    keep a lock on the log FILE itself after deploy.ps1 exits, so reading
    it back for the console is best-effort and never fatal -- only the
    process exit code decides pass/fail. ``timeout_s`` is a second line
    of defence in case anything else hangs.
    """
    script = SCRIPTS_DIR / name
    PS1_LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PS1_LOG_DIR / f"{name}.stdout.log"
    err_path = PS1_LOG_DIR / f"{name}.stderr.log"
    with out_path.open("w") as out_f, err_path.open("w") as err_f:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                stdout=out_f,
                stderr=err_f,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"{name} did not finish within {timeout_s}s (still running detached "
                "processes it started, e.g. waitress, are not affected by this timeout)"
            ) from exc

    try:
        print(out_path.read_text(errors="replace"))
    except OSError as exc:
        print(f"(could not read {out_path} for console echo: {exc})")

    if result.returncode != 0:
        try:
            print(err_path.read_text(errors="replace"), file=sys.stderr)
        except OSError as exc:
            print(f"(could not read {err_path} for console echo: {exc})", file=sys.stderr)
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def wait_for(predicate, timeout_s: int, interval_s: float, description: str):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except requests.RequestException:
            pass
        time.sleep(interval_s)
    raise TimeoutError(f"Timed out after {timeout_s}s waiting for: {description}")


def prometheus_target_health(job: str) -> str | None:
    resp = requests.get(f"{PROM_URL}/api/v1/targets", timeout=5)
    resp.raise_for_status()
    for target in resp.json()["data"]["activeTargets"]:
        if target["labels"].get("job") == job:
            return target["health"]
    return None


def alert_is_firing(alertname: str) -> bool:
    resp = requests.get(f"{PROM_URL}/api/v1/alerts", timeout=5)
    resp.raise_for_status()
    for alert in resp.json()["data"]["alerts"]:
        if alert["labels"].get("alertname") == alertname and alert["state"] == "firing":
            return True
    return False


def alert_is_gone(alertname: str) -> bool:
    resp = requests.get(f"{PROM_URL}/api/v1/alerts", timeout=5)
    resp.raise_for_status()
    return not any(
        a["labels"].get("alertname") == alertname for a in resp.json()["data"]["alerts"]
    )


def inbox_has_status(alertname: str, status: str, after_iso: str) -> bool:
    resp = requests.get(f"{INBOX_URL}/alerts.json", timeout=5)
    resp.raise_for_status()
    for entry in resp.json():
        if (
            entry.get("alertname") == alertname
            and entry.get("status") == status
            and entry.get("received_at", "") >= after_iso
        ):
            return True
    return False


def preflight() -> None:
    log("Checking Prometheus, Alertmanager, and the local webhook inbox are reachable...")
    requests.get(f"{PROM_URL}/-/healthy", timeout=5).raise_for_status()
    requests.get(f"{ALERTMANAGER_URL}/-/healthy", timeout=5).raise_for_status()
    requests.get(f"{INBOX_URL}/health", timeout=5).raise_for_status()
    requests.get(PROD_METRICS_URL, timeout=5).raise_for_status()
    log("All monitoring components reachable.")


def main() -> int:
    try:
        preflight()

        timeline["baseline_at"] = now()
        health = prometheus_target_health("incident-tracker-production")
        if health != "up":
            raise RuntimeError(
                f"production target is not healthy before the test (health={health}); "
                "fix the deployment before verifying alerting"
            )
        log("Baseline: production target is up.")

        log("Step 1/5: introducing a reversible incident (stopping the production process)...")
        t0 = now()
        timeline["incident_introduced_at"] = t0
        run_ps1("simulate_incident.ps1")

        log("Step 2/5: waiting for Prometheus to mark the target down...")
        wait_for(
            lambda: prometheus_target_health("incident-tracker-production") == "down",
            timeout_s=30, interval_s=2,
            description="production target health == down",
        )
        timeline["target_down_detected_at"] = now()
        log("Target confirmed down.")

        log("Step 3/5: waiting for the AppDown alert rule to fire...")
        wait_for(
            lambda: alert_is_firing(ALERT_NAME),
            timeout_s=60, interval_s=2,
            description=f"alert {ALERT_NAME} state == firing",
        )
        timeline["alert_fired_at"] = now()
        log("Alert is firing in Prometheus.")

        log("Step 4/5: waiting for the local webhook inbox to receive the firing notification...")
        wait_for(
            lambda: inbox_has_status(ALERT_NAME, "firing", t0),
            timeout_s=60, interval_s=2,
            description="webhook inbox received a firing notification",
        )
        timeline["notification_received_at"] = now()
        log("Notification received by webhook inbox.")

        log("Step 5/5: recovering the production process and waiting for resolution...")
        t_recover = now()
        timeline["recovery_started_at"] = t_recover
        run_ps1("recover_incident.ps1")

        wait_for(
            lambda: prometheus_target_health("incident-tracker-production") == "up",
            timeout_s=30, interval_s=2,
            description="production target health == up again",
        )
        timeline["target_up_detected_at"] = now()
        log("Target confirmed up again.")

        wait_for(
            lambda: alert_is_gone(ALERT_NAME),
            timeout_s=60, interval_s=2,
            description=f"alert {ALERT_NAME} cleared in Prometheus",
        )
        timeline["alert_cleared_at"] = now()
        log("Alert cleared in Prometheus.")

        wait_for(
            lambda: inbox_has_status(ALERT_NAME, "resolved", t_recover),
            timeout_s=60, interval_s=2,
            description="webhook inbox received a resolved notification",
        )
        timeline["resolved_notification_received_at"] = now()
        log("Resolved notification received by webhook inbox.")

        timeline["result"] = "PASSED"
    except Exception as exc:  # noqa: BLE001 - we want to report and exit non-zero
        timeline["result"] = "FAILED"
        timeline["error"] = str(exc)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
        log(f"FAILED: {exc}")
        return 1

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    log("Full alert path verified: issue -> rule fired -> notification received -> recovered -> resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
