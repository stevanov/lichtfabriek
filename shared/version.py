"""Lichtfabriek shared versioning (V8).

Version format: v<year>.<month>_<minor>.<bugfix> with an optional pre-release
suffix: -(alpha|beta|rc)<n>.

  release:     v26.11_0.0            regex: vDD.DD_D+.D+ (digits)
  pre-release: v26.11_0.0-alpha1     v26.11_0.0-beta2   v26.11_0.0-rc1

Ladder per Steven 2026-11-26: iterate alphas -> betas -> rcs -> final
(v26.11_0.0). One version line for both services. Release artifacts carry a
baked VERSION file; on the target there is no .git, so the version comes from
the file.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# full version with optional pre-release suffix
VERSION_RE = re.compile(r"^v\d{2}\.\d{2}_\d+\.\d+(-(alpha|beta|rc)\d+)?$")
# clean release form (no suffix)
CLEAN_RE = re.compile(r"^(v\d{2}\.\d{2}_\d+\.\d+)(-(alpha|beta|rc)\d+)?$")

_REPO_ROOT = Path(__file__).resolve().parent.parent


def describe() -> str:
    """Version from git describe.

    e.g. v26.11_0.0, v26.11_0.0-alpha1, or v26.11_0.0-alpha1-3-gabc1234
    when there are commits since the last tag.
    """
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
    """The version, including any pre-release suffix, for display.

    VERSION file wins on targets without .git. Falls back to git describe.
    """
    version_file = _REPO_ROOT / "VERSION"
    if version_file.exists():
        v = version_file.read_text().strip()
        if VERSION_RE.match(v):
            return v
    d = describe()
    m = CLEAN_RE.match(d)
    if m:
        return m.group(1) + (m.group(2) or "")
    return "v00.00_0.0"


def is_pre_release(version: str) -> bool:
    """True for -alphaN / -betaN / -rcN versions."""
    return bool(re.search(r"-(alpha|beta|rc)\d+$", version))


def next_version(version: str) -> str:
    """Next version in the ladder:
    vX-alphaN -> vX-alphaN+1 (alpha until stable enough)
    vX-betaN  -> vX-betaN+1
    vX-rcN    -> vX-rcN+1
    vX (final) -> vX bump bugfix; vX-alphaN -> beta requires manual choice.
    """
    m = CLEAN_RE.match(version)
    if not m:
        raise ValueError(f"bad version {version!r}")
    base, suffix = m.group(1), m.group(2)
    if suffix:
        # suffix is "-alphaN" / "-betaN" / "-rcN"
        kind = suffix[1:].rstrip("0123456789")
        n = int(suffix[len(kind) + 1:])
        return f"{base}-{kind}{n + 1}"
    year, month, minor, bugfix = _parts(base)
    return f"v{year}.{month}_{minor}.{bugfix + 1}"


def _parts(base: str) -> tuple[str, str, int, int]:
    m = re.match(r"^v(\d{2})\.(\d{2})_(\d+)\.(\d+)$", base)
    if not m:
        raise ValueError(f"bad base version {base!r}")
    return m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
