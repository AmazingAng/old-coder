"""Manual mutation testing: apply each mutant, run pytest, restore, report.

Usage: .venv/bin/python tools/mutants.py [pytest-target]
Exit code 0 iff every mutant is killed. The optional pytest-target narrows the
suite (e.g. a single test) for layer-attribution or prove-it-can-fail runs.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src/ratelimiter/__init__.py"
PYTEST = ROOT / ".venv/bin/pytest"

MUTANTS = [
    (
        "M1 flip limit comparison >= to >",
        "if len(hits) >= self._limit:",
        "if len(hits) > self._limit:",
    ),
    (
        "M2 flip expiry boundary > to >=",
        "while hits and now - hits[0] > self._window:",
        "while hits and now - hits[0] >= self._window:",
    ),
    (
        "M3 drop recording of allowed hit",
        "        hits.append(now)\n",
        "\n",
    ),
    (
        "M4 validation off-by-one <= to <",
        "if limit <= 0:",
        "if limit < 0:",
    ),
    (
        "M5 deny becomes allow (fail open)",
        "            return False",
        "            return True",
    ),
    (
        "M6 prune from wrong end",
        "hits.popleft()",
        "hits.pop()",
    ),
    (
        "M7 drop finiteness validation",
        "if not math.isfinite(window_seconds) or window_seconds <= 0:",
        "if window_seconds <= 0:",
    ),
    (
        "M8 denial records the attempt (memory leak)",
        "        if len(hits) >= self._limit:\n            return False",
        "        if len(hits) >= self._limit:\n"
        "            hits.append(now)\n"
        "            return False",
    ),
]


def main() -> int:
    pytest_target = sys.argv[1] if len(sys.argv) > 1 else "tests"
    original = TARGET.read_text()
    killed = 0
    errors = 0
    try:
        for name, old, new in MUTANTS:
            assert original.count(old) == 1, f"{name}: pattern not unique"
            TARGET.write_text(original.replace(old, new))
            result = subprocess.run(
                [str(PYTEST), "-q", "-x", pytest_target],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            # Only exit code 1 (tests ran and at least one failed) is a kill.
            # 0 = survived; anything else (collection error, usage error, no
            # tests collected) means nothing was verified — never count it.
            if result.returncode == 1:
                status = "KILLED"
                killed += 1
            elif result.returncode == 0:
                status = "SURVIVED"
            else:
                status = f"ERROR (pytest exit {result.returncode}, no tests verified)"
                errors += 1
            print(f"{name}: {status}")
    finally:
        TARGET.write_text(original)
    summary = f"\n{killed}/{len(MUTANTS)} mutants killed"
    if errors:
        summary += f", {errors} ERROR — run is invalid"
    print(summary)
    return 0 if killed == len(MUTANTS) and errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
