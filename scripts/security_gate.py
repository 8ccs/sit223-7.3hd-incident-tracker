#!/usr/bin/env python
"""Security gate.

Reads the Bandit (static analysis) and pip-audit (dependency
vulnerability) JSON reports produced by the Jenkins Security stage and
applies an explicit gate:

  - any Bandit finding with severity HIGH and confidence >= MEDIUM fails
    the build (unless explicitly suppressed in code with a justified
    ``# nosec`` comment, which Bandit itself excludes from its output).
  - any pip-audit finding for a dependency that has a known fixed version
    available fails the build (an unpatched CVE with no fix yet is
    reported but does not block, since there is nothing actionable to
    change; this must still be explained in the report).

This never silently downgrades severity or ignores findings; it only
gives an explicit, auditable pass/fail decision.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPORTS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/security")


def check_bandit() -> tuple[bool, str]:
    bandit_file = REPORTS_DIR / "bandit.json"
    if not bandit_file.exists():
        return False, "bandit.json not found; did the bandit step run?"
    data = json.loads(bandit_file.read_text())
    results = data.get("results", [])
    blocking = [
        r for r in results
        if r.get("issue_severity") == "HIGH" and r.get("issue_confidence") in ("MEDIUM", "HIGH")
    ]
    if blocking:
        names = ", ".join(sorted({r["test_id"] for r in blocking}))
        return False, f"{len(blocking)} HIGH-severity Bandit finding(s): {names}"
    return True, f"Bandit: {len(results)} finding(s) total, none at blocking severity"


def check_pip_audit() -> tuple[bool, str]:
    audit_file = REPORTS_DIR / "pip-audit.json"
    if not audit_file.exists():
        return False, "pip-audit.json not found; did the pip-audit step run?"
    data = json.loads(audit_file.read_text())
    dependencies = data.get("dependencies", data if isinstance(data, list) else [])
    blocking = []
    unfixable = []
    for dep in dependencies:
        vulns = dep.get("vulns", [])
        for v in vulns:
            fix_versions = v.get("fix_versions", [])
            entry = f"{dep.get('name')}=={dep.get('version')} ({v.get('id')})"
            if fix_versions:
                blocking.append(entry)
            else:
                unfixable.append(entry)
    if blocking:
        return False, f"{len(blocking)} dependency vulnerability(ies) with an available fix: {', '.join(blocking)}"
    msg = f"pip-audit: no fixable vulnerabilities found"
    if unfixable:
        msg += f"; {len(unfixable)} unfixed-upstream finding(s) reported but not blocking: {', '.join(unfixable)}"
    return True, msg


def main() -> int:
    results = [check_bandit(), check_pip_audit()]
    ok = True
    for passed, message in results:
        prefix = "PASS" if passed else "FAIL"
        print(f"[{prefix}] {message}")
        ok = ok and passed

    if ok:
        print("Security gate: PASSED")
        return 0
    print("Security gate: FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
