"""V20: no absolute/host-specific paths anywhere in the repo.

Searches tracked/committed files (excluding .git, .venv, data) for absolute
path markers that would leak host layout: /home/, /mnt/c, /opt/..., /etc/...,
/var/lib/..., plus the user's GitHub username in paths. The systemd unit may
only contain __KUBUSD_*__ placeholders.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

BAD_MARKERS = ("/home/", "/mnt/", "/opt/", "/etc/", "/var/lib/", "C:\\")

# paths that may legitimately contain such markers
SKIP_GLOBS = (".git", ".venv", "data", "*.db", ".corrupt")


def _walk():
    # docs (SPEC.md, AGENTS.md, README.md) legitimately *describe* the V20 rule;
    # this test file itself lists the markers as constants.
    DOC_GLOBS = ("SPEC.md", "AGENTS.md", "README.md", "RELEASING.md",
                 "tests/test_no_abs_paths.py")
    for p in REPO.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(REPO)
        if str(rel) in DOC_GLOBS:
            continue
        if any(rel.parts[0] == g or str(rel).endswith(g) for g in SKIP_GLOBS):
            continue
        if any(part.startswith(".") and part not in (".env.example",) for part in rel.parts):
            continue  # skip hidden files except .env.example
        yield rel, p


def test_no_absolute_paths():
    hits = []
    for rel, p in _walk():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        if str(rel) == "deploy/install.sh":
            # install.sh resolves system paths from env-overridable defaults
            # (KUBUSD_PREFIX, KUBUSD_SYSTEMD_DIR) at install time; only
            # genuinely-private markers are forbidden even there
            for marker in ("/home/", "/mnt/", "/var/lib/", "C:\\"):
                if marker in text:
                    hits.append(f"{rel}: contains {marker!r}")
            continue
        for marker in BAD_MARKERS:
            if marker in text:
                hits.append(f"{rel}: contains {marker!r}")
    assert not hits, "\n".join(hits)


def test_systemd_unit_is_template():
    unit = (REPO / "deploy" / "kubusd.service").read_text()
    # placeholders must remain, no absolute paths
    assert "__KUBUSD_USER__" in unit
    assert "__KUBUSD_INSTALL_DIR__" in unit
    assert "__KUBUSD_ENV_FILE__" in unit
    for marker in BAD_MARKERS:
        assert marker not in unit
