from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from hermes_cli import main as hermes_main


def test_official_repo_urls_point_to_mochi() -> None:
    assert hermes_main.OFFICIAL_REPO_URL == "https://github.com/Verbiflow/mochi.git"
    assert all("NousResearch/hermes-agent" not in url for url in hermes_main.OFFICIAL_REPO_URLS)


def test_legacy_origin_fails_with_gateway_safe_guidance(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        hermes_main._exit_if_legacy_hermes_origin(
            "https://github.com/NousResearch/hermes-agent.git",
            gateway_mode=True,
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "legacy Hermes upstream" in out
    assert "gateway cannot migrate remotes unattended" in out
    assert "migrate_to_mochi.sh" in out


def test_update_check_fetches_origin_not_upstream(monkeypatch, tmp_path, capsys) -> None:
    project_root = tmp_path / "checkout"
    project_root.mkdir()
    (project_root / ".git").mkdir()
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append([str(part) for part in cmd])
        joined = " ".join(str(part) for part in cmd)
        if "remote get-url origin" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/Verbiflow/mochi.git\n", stderr="")
        if "fetch origin" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "rev-list HEAD..origin/main --count" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="2\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(hermes_main, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(hermes_main.subprocess, "run", fake_run)

    hermes_main._cmd_update_check()

    out = capsys.readouterr().out
    assert "behind origin/main" in out
    assert any(call[:3] == ["git", "fetch", "origin"] for call in calls)
    assert not any(call[:3] == ["git", "fetch", "upstream"] for call in calls)


def test_fork_upstream_notice_never_pulls_or_pushes(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append([str(part) for part in cmd])
        joined = " ".join(str(part) for part in cmd)
        if "remote get-url upstream" in joined:
            return SimpleNamespace(returncode=0, stdout="https://github.com/Verbiflow/mochi.git\n")
        if "fetch upstream --quiet" in joined:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rev-list --count upstream/main..origin/main" in joined:
            return SimpleNamespace(returncode=0, stdout="0\n")
        if "rev-list --count origin/main..upstream/main" in joined:
            return SimpleNamespace(returncode=0, stdout="3\n")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(hermes_main.subprocess, "run", fake_run)

    hermes_main._maybe_offer_mochi_upstream(["git"], tmp_path, gateway_mode=False)

    flattened = [" ".join(call) for call in calls]
    assert not any(" pull " in f" {cmd} " for cmd in flattened)
    assert not any(" push " in f" {cmd} " for cmd in flattened)
