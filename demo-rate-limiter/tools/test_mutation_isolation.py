"""Exercise the real mutation runner on disposable fixtures, never user files."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).with_name("mutants.py")
RELATIVE = Path("src/ratelimiter/__init__.py")
PROBE = """
from pathlib import Path
import mutants
with mutants.sandbox() as work:
    print(mutants.run_mutant(work, 'VALUE = 1\\n', '1', '2', 'tests'))
"""


def fixture_demo(tmp_path: Path) -> Path:
    demo = tmp_path / "demo"
    for relative in ("tools", "src/ratelimiter", ".venv/bin"):
        (demo / relative).mkdir(parents=True)
    shutil.copy2(RUNNER, demo / "tools/mutants.py")
    (demo / RELATIVE).write_text("VALUE = 1\n")
    (demo / ".venv/bin/python").symlink_to(sys.executable)
    runner = demo / ".venv/bin/pytest"
    runner.write_text(
        "#!/bin/sh\nexec "
        + shlex.quote(sys.executable)
        + " -c 'import ratelimiter; assert ratelimiter.VALUE == 1'\n"
    )
    runner.chmod(0o755)
    return demo


def probe(demo: Path, program: str = PROBE) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=demo / "tools",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize("kind", ["file", "directory", "dangling"])
def test_links_rejected_before_import_or_write(tmp_path: Path, kind: str) -> None:
    demo = fixture_demo(tmp_path)
    marker = tmp_path / "imported"
    original = f"from pathlib import Path\nPath({str(marker)!r}).touch()\nVALUE = 1\n"
    (demo / RELATIVE).write_text(original)
    target = demo / (RELATIVE.parent if kind == "directory" else RELATIVE)
    outside = tmp_path / "outside"
    target.rename(outside)
    target.symlink_to(outside if kind != "dangling" else tmp_path / "missing")
    external_source = outside / "__init__.py" if outside.is_dir() else outside

    result = probe(demo)

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert result.stdout == ""
    assert not marker.exists(), "linked source was imported before rejection"
    assert external_source.read_text() == original


def test_target_link_introduced_between_runs_is_rejected(tmp_path: Path) -> None:
    demo = fixture_demo(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n")
    program = PROBE.replace(
        "    print(",
        "    target = work / mutants.TARGET_REL\n"
        "    target.unlink()\n"
        f"    target.symlink_to({str(outside)!r})\n"
        "    print(",
    )

    result = probe(demo, program)

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert outside.read_text() == "VALUE = 1\n"


def test_regular_copy_runs_mutated_code_without_touching_original(
    tmp_path: Path,
) -> None:
    demo = fixture_demo(tmp_path)

    result = probe(demo)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1", "the assertion must see the mutated copy"
    assert (demo / RELATIVE).read_bytes() == b"VALUE = 1\n"
