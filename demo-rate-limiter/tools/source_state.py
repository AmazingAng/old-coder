"""Produce a deterministic, fail-closed binding for the demo source tree."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
ROOT = DEMO.parent
SCOPES = (
    ".github/workflows",
    "demo-rate-limiter/examples",
    "demo-rate-limiter/pyproject.toml",
    "demo-rate-limiter/requirements-dev.txt",
    "demo-rate-limiter/spec.md",
    "demo-rate-limiter/src",
    "demo-rate-limiter/tests",
    "demo-rate-limiter/tools",
)
EXCLUDED_DIRS = {
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
EXCLUDED_FILES = {".coverage", ".DS_Store", "coverage.xml"}


def _git(
    root: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_root() -> Path | None:
    discovered = _git(DEMO, "rev-parse", "--show-toplevel", check=False)
    if discovered.returncode != 0:
        return None
    root = Path(os.fsdecode(discovered.stdout.rstrip(b"\n")))
    relative_script = (DEMO / "tools/source_state.sh").relative_to(root).as_posix()
    tracked = _git(
        root, "ls-files", "--error-unmatch", "--", relative_script, check=False
    )
    return root if tracked.returncode == 0 else None


def _manifest_from_git(root: Path) -> list[str]:
    status = _git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignored=no",
        "--",
        *SCOPES,
    ).stdout
    if status:
        records = [record for record in status.split(b"\0") if record]
        issue = (
            "untracked files"
            if any(record.startswith(b"?? ") for record in records)
            else "dirty files"
        )
        details = ", ".join(os.fsdecode(record) for record in records)
        raise RuntimeError(f"source scope contains {issue}: {details}")

    output = _git(root, "ls-files", "-z", "--", *SCOPES).stdout
    files = sorted(os.fsdecode(path) for path in output.split(b"\0") if path)
    for scope in SCOPES:
        if not any(path == scope or path.startswith(f"{scope}/") for path in files):
            raise RuntimeError(f"source scope has no tracked input: {scope}")
    return files


def _is_generated(relative: Path) -> bool:
    return (
        any(
            part in EXCLUDED_DIRS or part.endswith(".egg-info")
            for part in relative.parts
        )
        or relative.name in EXCLUDED_FILES
        or relative.suffix == ".pyc"
    )


def _manifest_without_git(root: Path) -> list[str]:
    files: list[str] = []
    for scope in SCOPES:
        candidate = root / scope
        if not candidate.exists():
            raise RuntimeError(f"source input is missing: {scope}")
        inputs = [candidate] if candidate.is_file() else candidate.rglob("*")
        scoped_files = [
            path
            for path in inputs
            if (path.is_file() or path.is_symlink())
            and not _is_generated(path.relative_to(root))
        ]
        if not scoped_files:
            raise RuntimeError(f"source scope has no input: {scope}")
        files.extend(path.relative_to(root).as_posix() for path in scoped_files)
    return sorted(files)


def _read_input(path: Path) -> bytes:
    if path.is_symlink():
        return os.fsencode(os.readlink(path))
    if not path.is_file():
        raise RuntimeError(f"source input is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as error:
        raise RuntimeError(f"cannot read source input {path}: {error}") from error


def _tree_hash(root: Path, files: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in files:
        path_bytes = relative.encode("utf-8")
        content = _read_input(root / relative)
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()[:16]


def main() -> int:
    try:
        git_root = _git_root()
        root = git_root or ROOT
        if git_root:
            head_before = os.fsdecode(
                _git(root, "rev-parse", "--short", "HEAD").stdout
            ).strip()
            files = _manifest_from_git(root)
            tree = _tree_hash(root, files)
            if _manifest_from_git(root) != files:
                raise RuntimeError("source manifest changed while hashing")
            head = os.fsdecode(
                _git(root, "rev-parse", "--short", "HEAD").stdout
            ).strip()
            if head != head_before:
                raise RuntimeError("HEAD changed while hashing")
            source_commit = os.fsdecode(
                _git(root, "log", "-1", "--format=%h", "--", *SCOPES).stdout
            ).strip()
            if not source_commit:
                raise RuntimeError("no commit contains the source manifest")
        else:
            head = source_commit = "(no git)"
            tree = _tree_hash(root, _manifest_without_git(root))
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as error:
        print(f"source-state error: {error}", file=sys.stderr)
        return 2

    print(f"head:          {head}")
    print(f"source commit: {source_commit}")
    print(f"tree:          {tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
