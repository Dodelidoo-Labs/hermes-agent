"""Implicit updates must retain the maintained fork's compatibility branch."""
import subprocess
from types import SimpleNamespace

import pytest

from hermes_cli import main
from hermes_cli.main_install_repair import _resolve_update_branch


@pytest.mark.parametrize("origin,expected", [
    ("https://github.com/Dodelidoo-Labs/hermes-agent.git", "main"),
    ("git@github.com:Dodelidoo-Labs/hermes-agent.git", "main"),
    ("ssh://git@github.com/Dodelidoo-Labs/hermes-agent.git", "main"),
    ("https://github.com/NousResearch/hermes-agent.git", "main"),
    ("https://github.com/another-owner/hermes-agent.git", "main"),
    ("https://example.invalid/Dodelidoo-Labs/hermes-agent.git", "main"),
    (None, "main"),
])
def test_update_target_uses_real_origin_without_overriding_explicit_branch(tmp_path, monkeypatch, origin, expected):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if origin:
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", origin], check=True)
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    for value in (None, "", "  "):
        assert _resolve_update_branch(SimpleNamespace(branch=value)) == expected
    assert _resolve_update_branch(SimpleNamespace()) == expected
    for explicit in ("main", "feature/test"):
        assert _resolve_update_branch(SimpleNamespace(branch=f" {explicit} ")) == explicit
