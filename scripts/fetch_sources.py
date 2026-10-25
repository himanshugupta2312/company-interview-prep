"""Fetch or update the upstream interview-preparation repositories."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIRECTORY = REPOSITORY_ROOT / "sources"


@dataclass(frozen=True)
class Source:
    name: str
    url: str


SOURCES = (
    Source(
        name="leetcode-company-wise-problems",
        url="https://github.com/liquidslr/leetcode-company-wise-problems.git",
    ),
    Source(
        name="system-design-notes",
        url="https://github.com/liquidslr/system-design-notes.git",
    ),
)


class SourceUpdateError(Exception):
    """Raised when a source directory cannot safely be fetched or updated."""


def run_git(
    *arguments: str,
    cwd: Path | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def fetch_source(source: Source) -> bool:
    """Fetch one source, returning True when it was newly cloned."""
    destination = SOURCES_DIRECTORY / source.name

    if destination.is_symlink():
        raise SourceUpdateError(f"Refusing to use symlinked source directory: {destination}")

    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        run_git("clone", "--depth", "1", "--", source.url, str(destination))
        return True

    if not destination.is_dir() or not (destination / ".git").exists():
        raise SourceUpdateError(
            f"Source path exists but is not a Git clone: {destination}. "
            "Move it out of the way and try again."
        )

    try:
        remote = run_git(
            "remote",
            "get-url",
            "origin",
            cwd=destination,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()
        raise SourceUpdateError(
            f"Could not read the origin URL for {destination}"
            + (f": {detail}" if detail else "")
        ) from error

    if remote.stdout.strip().rstrip("/") != source.url.rstrip("/"):
        raise SourceUpdateError(
            f"Unexpected origin for {destination}: {remote.stdout.strip()}. "
            f"Expected {source.url}."
        )

    run_git("pull", "--ff-only", cwd=destination)
    return False


def main() -> int:
    if shutil.which("git") is None:
        print("Error: Git is required but was not found on PATH.", file=sys.stderr)
        return 1

    try:
        for source in SOURCES:
            action = "Cloned" if fetch_source(source) else "Updated"
            print(f"{action} {source.name}")
    except SourceUpdateError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(
            f"Error: Git command failed with exit code {error.returncode}: "
            f"{subprocess.list2cmdline(error.cmd)}",
            file=sys.stderr,
        )
        return error.returncode or 1

    print(f"Sources are available under {SOURCES_DIRECTORY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
