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
        "            hits.append(now)\n",
        "\n",
    ),
    (
        "M4 validation off-by-one <= to <",
        "if limit <= 0:",
        "if limit < 0:",
    ),
    (
        "M5 deny becomes allow (fail open)",
        "                return False",
        "                return True",
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
        "            if len(hits) >= self._limit:\n                return False",
        "            if len(hits) >= self._limit:\n"
        "                hits.append(now)\n"
        "                return False",
    ),
    # [REVISION 4] M9-M13 each pin a failure-model row that an independent
    # verification pass showed was claiming coverage it did not have.
    (
        "M9 drop limit type/finiteness validation (limit=NaN allows forever)",
        "        if isinstance(limit, bool) or not isinstance(limit, int):\n"
        '            raise ValueError(f"limit must be an integer, got {limit!r}")\n',
        "",
    ),
    (
        "M10 clock skew fails open (absolute age)",
        "while hits and now - hits[0] > self._window:",
        "while hits and abs(now - hits[0]) > self._window:",
    ),
    # M11 (prune at most one expired hit per call: `while` -> `if`) is
    # deliberately absent. A verification pass reported it as a surviving
    # mutant proving "under-allowing drift"; it is in fact EQUIVALENT. If the
    # head is expired, pruning one already leaves len <= limit-1, so both
    # forms allow; if the head is not expired then under a monotone clock no
    # entry is expired, so the deques are identical. Confirmed by differential
    # test over 200k randomized monotone sequences: 0 divergences. Killing it
    # would require a test asserting non-behavior — anti-gaming rule 4.
    (
        "M12 never forget idle keys (unbounded key-space growth)",
        "        idle = [k for k, hits in self._hits.items() "
        "if now - hits[-1] > self._window]\n",
        "        idle: list[str] = []\n",
    ),
    (
        "M13 drop the lock (concurrent over-allow)",
        "        with self._lock:",
        "        if True:",
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
