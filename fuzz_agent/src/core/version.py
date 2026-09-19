"""IndusFuzz version — single source of truth.

Prefers git describe when available (production build with tags),
falls back to HARDCODED_VERSION for dev environments without git tags.

All version references (main.py banner, report_generator, CLI --version)
import from here — do NOT hardcode version strings elsewhere.
"""
import os
import subprocess


HARDCODED_VERSION = "1.8.1"


def _from_git():
    """Try `git describe --tags --always --dirty`.

    Returns the git-derived version string, or None if git is unavailable.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        # Walk up to project root (src/core/ → project/)
        project_root = os.path.dirname(os.path.dirname(here))
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = result.stdout.strip()
            # Strip leading 'v' if present: v1.8.0 → 1.8.0
            if raw.startswith("v"):
                raw = raw[1:]
            return raw
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def get_version():
    """Return the current version string.

    Resolution order:
      1. Environment override INDUSFUZZ_VERSION (CI / packaging)
      2. git describe --tags --always --dirty
      3. HARDCODED_VERSION
    """
    env = os.environ.get("INDUSFUZZ_VERSION")
    if env:
        return env
    git_ver = _from_git()
    if git_ver:
        # Strip -dirty suffix — production build should not leak working-copy state
        git_ver = git_ver.split("-dirty")[0]
        return git_ver
    return HARDCODED_VERSION


__version__ = get_version()


