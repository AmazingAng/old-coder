"""Manual mutation testing: apply each mutant, run pytest, restore, report.

Usage: .venv/bin/python tools/mutants.py [pytest-target]
Exit code 0 iff every mutant is killed. The optional pytest-target narrows the
suite (e.g. a single test) for layer-attribution or prove-it-can-fail runs.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src/ratelimiter/__init__.py"
PYCACHE = TARGET.parent / "__pycache__"
PYTEST = ROOT / ".venv/bin/pytest"

# CPython validates a cached .pyc against (source mtime in whole seconds,
# source size). Two mutants of identical size written inside the same second
# are indistinguishable to that check, so the second one silently runs the
# first one's bytecode. M4 and M5 are both exactly one byte shorter than the
# original and adjacent in the list, so M5 -- the fail-open mutant -- was
# reported KILLED on the strength of M4's code. The bias is toward inflating
# the kill count, which can never surface as a red gauntlet. Both defences are
# needed only as a belt-and-braces pair, and an earlier version of this
# comment had the roles backwards. Measured three ways: removing the rmtree
# alone leaves the control green; removing DONTWRITEBYTECODE alone trips the
# tripwire below with a RuntimeError; only removing both AND the tripwire
# reproduces the misreport. DONTWRITEBYTECODE is what actually closes the
# leak — with no .pyc written during a run there is nothing to inherit — and
# gauntlet.sh clears __pycache__ before the layer starts anyway. The rmtree
# covers the case of running this script directly on a dirty tree.
MUTANT_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

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
        "    if isinstance(limit, bool) or not isinstance(limit, int):\n"
        '        raise ValueError(f"limit must be an integer, got {limit!r}")\n',
        "",
    ),
    (
        "M14 normalise the key (distinct callers share one bucket)",
        '            raise ValueError("key must not be empty")\n',
        '            raise ValueError("key must not be empty")\n'
        "        key = key.lower()\n",
    ),
    (
        "M15 drop window_seconds type guard (window=True means 1 second)",
        "    if isinstance(window_seconds, bool) or not isinstance("
        "window_seconds, int | float):\n"
        '        raise ValueError(f"window_seconds must be a number, '
        'got {window_seconds!r}")\n',
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
    # [REVISION 4c] A third verification round found the lock covered the
    # check-and-append but not the clock read, and that no test could tell the
    # two placements apart because every concurrency test held time constant.
    (
        "M16 read the clock outside the lock (commits invert, deque unsorted)",
        "        with self._lock:\n            now = self._clock()\n",
        "        now = self._clock()\n        with self._lock:\n",
    ),
    (
        "M17 strip the key (trailing-space caller merged with the bare one)",
        '            raise ValueError("key must not be empty")\n',
        '            raise ValueError("key must not be empty")\n'
        "        key = key.strip()\n",
    ),
    (
        "M18 sweep expiry boundary > to >= (forgets a key with a live hit)",
        "if now - hits[-1] > self._window]\n",
        "if now - hits[-1] >= self._window]\n",
    ),
    # [REVISION 4d] Round 4 found the throttle was an asserted design property
    # with no catcher, and that a one-sided comparison suspended it entirely
    # under backward skew.
    (
        "M19 drop the sweep throttle (O(keys) scan on every request)",
        "        self._last_sweep = now\n",
        "",
    ),
    (
        "M20 one-sided sweep throttle (backward skew suspends reclamation)",
        "if 0 <= now - self._last_sweep <= self._window:",
        "if now - self._last_sweep <= self._window:",
    ),
    # [REVISION 4e] The throttle's own boundary was the last age comparison in
    # the file with no test behind it -- _prune's had M2, _sweep's had M18.
    # The sentinel had the same shape: every clock in the suite starts at 0.0
    # or beyond a window, so its purpose was structurally invisible.
    (
        "M21 sweep-throttle boundary <= to < (sweeps early, delays cleanup)",
        "if 0 <= now - self._last_sweep <= self._window:",
        "if 0 <= now - self._last_sweep < self._window:",
    ),
    (
        "M22 sweep sentinel -inf to 0.0 (first call skips its sweep)",
        "self._last_sweep = -math.inf",
        "self._last_sweep = 0.0",
    ),
    # [REVISION 4f] The idle threshold's boundary was pinned but its magnitude
    # was not: 1.5x and 1.99x both survived the entire gauntlet, inflating the
    # approved two-window bound by up to 50%.
    (
        "M23 inflate the idle threshold 1.5x (retention bound silently grows)",
        "if now - hits[-1] > self._window]\n",
        "if now - hits[-1] > self._window * 1.5]\n",
    ),
]


# Negative control for the harness itself: two mutants of IDENTICAL size, a
# killer followed by a proven-equivalent one. (Both are length-PRESERVING, so
# all three files are the same size; an earlier version of this comment also
# said "each one byte shorter than the original", which describes M4/M5, not
# these. Only C1 == C2 matters for the collision.)
# If bytecode caching ever leaks between runs again, the equivalent mutant
# inherits the killer's result and is misreported as KILLED. Run with
# --negative-control; run as a gate by tools/gauntlet.sh before the real
# mutation pass. (It is NOT part of test_gauntlet_checks.sh, which covers
# must_not_match only — an earlier comment here claimed otherwise.)
# Both mutations are length-preserving, so the two mutated files are the same
# size; with a pinned mtime the (mtime, size) collision is constructed, not
# waited for. C2 must be STRICTLY equivalent: `or` over two side-effect-free
# isinstance checks is commutative. An earlier attempt used the sweep throttle
# (`<=` -> `<`), which differs at now - last_sweep == window and so can change
# the key map — not equivalent once the memory bound is part of the contract,
# and it would have turned red the day a test pinned that boundary.
CONTROL = [
    ("C1 killer (control)", "if limit <= 0:", "if limit >= 0:"),
    (
        "C2 equivalent (control)",
        "if isinstance(limit, bool) or not isinstance(limit, int):",
        "if not isinstance(limit, int) or isinstance(limit, bool):",
    ),
]


def run_mutant(
    original: str, old: str, new: str, pytest_target: str, pin_mtime: float = 0.0
) -> int:
    """Apply one mutant and return pytest's exit code, with no stale bytecode.

    `pin_mtime` is used only by the negative control: pinning both control
    mutants to one mtime makes the (mtime, size) collision deterministic
    instead of depending on two writes happening to land in the same second.
    """
    TARGET.write_text(original.replace(old, new))
    if pin_mtime:
        os.utime(TARGET, (pin_mtime, pin_mtime))
    shutil.rmtree(PYCACHE, ignore_errors=True)
    result = subprocess.run(
        [str(PYTEST), "-q", "-x", pytest_target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=MUTANT_ENV,
    )
    if PYCACHE.exists():
        raise RuntimeError(
            "bytecode cache reappeared during a mutant run: results are not "
            "trustworthy (PYTHONDONTWRITEBYTECODE had no effect)"
        )
    return result.returncode


def negative_control() -> int:
    """Prove the harness can still tell a killer from an equivalent mutant."""
    original = TARGET.read_text()
    try:
        pinned = 1_600_000_000.0  # identical mtime for both, see run_mutant
        codes = [
            run_mutant(original, old, new, "tests", pin_mtime=pinned)
            for _, old, new in CONTROL
        ]
    finally:
        TARGET.write_text(original)
        # The control pins an mtime and leaves cache state behind; neither may
        # leak into the real mutation run that follows.
        shutil.rmtree(PYCACHE, ignore_errors=True)
    if TARGET.read_text() != original:
        raise RuntimeError("negative control did not restore the source file")
    ok = codes == [1, 0]
    for (name, _, _), code in zip(CONTROL, codes, strict=True):
        verdict = {1: "KILLED", 0: "SURVIVED"}.get(code, f"ERROR (exit {code})")
        print(f"  {name}: {verdict}")
    print("  negative control: " + ("ok" if ok else "FAILED — harness misreports"))
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--negative-control":
        return negative_control()
    pytest_target = sys.argv[1] if len(sys.argv) > 1 else "tests"
    original = TARGET.read_text()
    killed = 0
    errors = 0
    try:
        for name, old, new in MUTANTS:
            assert original.count(old) == 1, f"{name}: pattern not unique"
            returncode = run_mutant(original, old, new, pytest_target)
            # Only exit code 1 (tests ran and at least one failed) is a kill.
            # 0 = survived; anything else (collection error, usage error, no
            # tests collected) means nothing was verified — never count it.
            if returncode == 1:
                status = "KILLED"
                killed += 1
            elif returncode == 0:
                status = "SURVIVED"
            else:
                status = f"ERROR (pytest exit {returncode}, no tests verified)"
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
