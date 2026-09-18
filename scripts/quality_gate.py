#!/usr/bin/env python
"""Code Quality gate.

Reads the pylint JSON report and radon cyclomatic-complexity JSON report
that the Jenkins Code Quality stage produces, then applies explicit,
documented thresholds:

  - pylint score must be >= PYLINT_MIN_SCORE (out of 10)
  - no function may have a radon cyclomatic-complexity rank worse than
    RADON_MAX_RANK ("C" = moderately complex; "D"/"E"/"F" fail the gate)

Exits non-zero (fails the Jenkins stage / build) if either threshold is
violated, so a failed quality gate blocks promotion further down the
pipeline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PYLINT_MIN_SCORE = 8.0
RADON_MAX_RANK = "C"  # A (best) .. F (worst); fail anything worse than C
RANK_ORDER = ["A", "B", "C", "D", "E", "F"]

REPORTS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/quality")


def check_pylint() -> tuple[bool, str]:
    score_file = REPORTS_DIR / "pylint-score.txt"
    if not score_file.exists():
        return False, "pylint-score.txt not found; did the pylint step run?"
    try:
        score = float(score_file.read_text().strip())
    except ValueError:
        return False, f"could not parse pylint score from {score_file}"
    passed = score >= PYLINT_MIN_SCORE
    return passed, f"pylint score {score:.2f}/10 (threshold {PYLINT_MIN_SCORE})"


def check_radon() -> tuple[bool, str]:
    cc_file = REPORTS_DIR / "radon-cc.json"
    if not cc_file.exists():
        return False, "radon-cc.json not found; did the radon step run?"
    data = json.loads(cc_file.read_text())
    worst_rank = "A"
    worst_item = None
    for _file, blocks in data.items():
        for block in blocks:
            rank = block.get("rank", "A")
            if RANK_ORDER.index(rank) > RANK_ORDER.index(worst_rank):
                worst_rank = rank
                worst_item = f"{block.get('name')} ({_file})"
    passed = RANK_ORDER.index(worst_rank) <= RANK_ORDER.index(RADON_MAX_RANK)
    detail = f"worst cyclomatic complexity rank: {worst_rank}"
    if worst_item:
        detail += f" in {worst_item}"
    detail += f" (max allowed: {RADON_MAX_RANK})"
    return passed, detail


def main() -> int:
    results = [check_pylint(), check_radon()]
    ok = True
    for passed, message in results:
        prefix = "PASS" if passed else "FAIL"
        print(f"[{prefix}] {message}")
        ok = ok and passed

    if ok:
        print("Code Quality gate: PASSED")
        return 0
    print("Code Quality gate: FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
