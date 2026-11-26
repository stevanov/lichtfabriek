"""Tests for shared versioning (V8, pre-release ladder)."""

import pytest

from shared import version


@pytest.mark.parametrize(
    "v,ok",
    [
        ("v26.11_0.0", True),
        ("v26.11_38.0", True),
        ("v26.11_0.0-alpha1", True),
        ("v26.11_0.0-beta2", True),
        ("v26.11_0.0-rc3", True),
        ("v26.11_0.0-rc3-4-gabc", False),  # describe suffix is not a version
        ("v26.11_0.0-gamma1", False),      # unknown pre-release kind
        ("26.11_0.0", False),
        ("v26.11_0.0-alpha", False),       # missing number
    ],
)
def test_version_re(v, ok):
    assert bool(version.VERSION_RE.match(v)) == ok


def test_next_version_alpha():
    assert version.next_version("v26.11_0.0-alpha1") == "v26.11_0.0-alpha2"


def test_next_version_beta():
    assert version.next_version("v26.11_0.0-beta3") == "v26.11_0.0-beta4"


def test_next_version_rc():
    assert version.next_version("v26.11_0.0-rc1") == "v26.11_0.0-rc2"


def test_next_version_final_bumps_bugfix():
    assert version.next_version("v26.11_0.0") == "v26.11_0.1"


def test_is_pre_release():
    assert version.is_pre_release("v26.11_0.0-alpha1")
    assert version.is_pre_release("v26.11_0.0-rc1")
    assert not version.is_pre_release("v26.11_0.0")


def test_release_version_from_file(tmp_path, monkeypatch):
    import shared.version as v

    monkeypatch.setattr(v, "_REPO_ROOT", tmp_path)
    (tmp_path / "VERSION").write_text("v26.11_0.0-alpha1\n")
    assert v.release_version() == "v26.11_0.0-alpha1"
