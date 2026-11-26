"""Lichtfabriek shared versioning (V8).

Version format: v<year>.<month>_<minor>.<bugfix> (regex ^v\d{2}\.\d{2}_\d+\.\d+$).
One version line for both services. Release artifacts carry a baked VERSION
file; on the target there is no .git, so the version comes from the file.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

VERSION_RE = re.compile(r"^v\d{2}\.\d{2}_\d+\.\d+$")

_REPO_ROOT = Path(__file__).resolve().parent.parent


def describe() -> str:
    """Version from git describe, e.g. v26.11_38.0 or v26.11_38.0-3-gabc1234."""
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--long", "--always"],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        v = out.stdout.strip()
        if v:
            return v
    except Exception:
        pass
    return "unknown"


def release_version() -> str:
    """The clean release version (VERSION file wins on targets without .git)."""
    version_file = _REPO_ROOT / "VERSION"
    if version_file.exists():
        v = version_file.read_text().strip()
        if VERSION_RE.match(v):
            return v
    d = describe()
    m = re.match(r"^(v\d{2}\.\d{2}_\d+\.\d+)", d)
    return m.group(1) if m else "v00.00_0.0"
