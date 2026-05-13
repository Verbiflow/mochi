from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "migrate_to_mochi.sh"


def _run(cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    full_env.update(
        {
            "GIT_AUTHOR_NAME": "Mochi Test",
            "GIT_AUTHOR_EMAIL": "mochi-test@example.com",
            "GIT_COMMITTER_NAME": "Mochi Test",
            "GIT_COMMITTER_EMAIL": "mochi-test@example.com",
        }
    )
    if env:
        full_env.update(env)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=full_env,
        text=True,
        capture_output=True,
        check=check,
    )


def _write_fake_hermes(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True)
    hermes = bin_dir / "hermes"
    hermes.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = gateway ] && [ \"$2\" = status ]; then\n"
        "  echo 'Gateway is not running'\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = gateway ] && { [ \"$2\" = stop ] || [ \"$2\" = restart ]; }; then\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    hermes.chmod(0o755)


def _make_seed_repo(tmp_path: Path) -> Path:
    seed = tmp_path / "seed"
    seed.mkdir()
    _run(["git", "init"], seed)
    _run(["git", "checkout", "-b", "main"], seed)
    (seed / "pyproject.toml").write_text('[project]\nname = "hermes-agent"\n', encoding="utf-8")
    _run(["git", "add", "pyproject.toml"], seed)
    _run(["git", "commit", "-m", "seed"], seed)
    return seed


def _make_install_and_mochi_remote(tmp_path: Path) -> tuple[Path, Path]:
    seed = _make_seed_repo(tmp_path)
    legacy_bare = tmp_path / "legacy.git"
    _run(["git", "clone", "--bare", str(seed), str(legacy_bare)], tmp_path)

    install = tmp_path / "install"
    _run(["git", "clone", str(legacy_bare), str(install)], tmp_path)
    _run(["git", "remote", "set-url", "origin", "https://github.com/NousResearch/hermes-agent.git"], install)
    _run(["git", "remote", "add", "upstream", "https://github.com/NousResearch/hermes-agent.git"], install)

    mochi_work = tmp_path / "mochi-work"
    _run(["git", "clone", str(legacy_bare), str(mochi_work)], tmp_path)
    (mochi_work / "mochi.txt").write_text("mochi\n", encoding="utf-8")
    _run(["git", "add", "mochi.txt"], mochi_work)
    _run(["git", "commit", "-m", "mochi update"], mochi_work)

    mochi_bare = tmp_path / "mochi.git"
    _run(["git", "clone", "--bare", str(mochi_work), str(mochi_bare)], tmp_path)
    return install, mochi_bare


def _migration_env(tmp_path: Path) -> dict[str, str]:
    fake_bin = tmp_path / "bin"
    _write_fake_hermes(fake_bin)
    return {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "MOCHI_MIGRATION_SKIP_DEPS": "1",
    }


def test_migration_script_switches_origin_removes_legacy_upstream_and_is_idempotent(tmp_path: Path) -> None:
    install, mochi_bare = _make_install_and_mochi_remote(tmp_path)
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / ".skip_upstream_prompt").write_text("", encoding="utf-8")
    env = _migration_env(tmp_path)

    cmd = [
        "bash",
        str(SCRIPT),
        "--install-dir",
        str(install),
        "--hermes-home",
        str(hermes_home),
        "--repo-url",
        str(mochi_bare),
    ]
    first = _run(cmd, tmp_path, env=env)
    second = _run(cmd, tmp_path, env=env)

    origin = _run(["git", "remote", "get-url", "origin"], install).stdout.strip()
    upstream = _run(["git", "remote", "get-url", "upstream"], install, check=False)
    head = _run(["git", "rev-parse", "HEAD"], install).stdout.strip()
    origin_main = _run(["git", "rev-parse", "origin/main"], install).stdout.strip()

    assert origin == str(mochi_bare)
    assert upstream.returncode != 0
    assert head == origin_main
    assert "Mochi migration complete" in first.stdout
    assert "Mochi migration complete" in second.stdout
    assert list((hermes_home / "backups").glob("mochi-migration-*"))
    assert not (hermes_home / ".skip_upstream_prompt").exists()


def test_migration_script_stashes_uncommitted_changes(tmp_path: Path) -> None:
    install, mochi_bare = _make_install_and_mochi_remote(tmp_path)
    hermes_home = tmp_path / ".hermes"
    env = _migration_env(tmp_path)
    (install / "local-notes.txt").write_text("keep me\n", encoding="utf-8")

    _run(
        [
            "bash",
            str(SCRIPT),
            "--install-dir",
            str(install),
            "--hermes-home",
            str(hermes_home),
            "--repo-url",
            str(mochi_bare),
        ],
        tmp_path,
        env=env,
    )

    stash_list = _run(["git", "stash", "list"], install).stdout
    assert "mochi-migration-autostash" in stash_list


def test_migration_script_fails_before_deps_when_history_diverged(tmp_path: Path) -> None:
    install, mochi_bare = _make_install_and_mochi_remote(tmp_path)
    hermes_home = tmp_path / ".hermes"
    env = _migration_env(tmp_path)
    (install / "local-commit.txt").write_text("local\n", encoding="utf-8")
    _run(["git", "add", "local-commit.txt"], install)
    _run(["git", "commit", "-m", "local diverged commit"], install)

    result = _run(
        [
            "bash",
            str(SCRIPT),
            "--install-dir",
            str(install),
            "--hermes-home",
            str(hermes_home),
            "--repo-url",
            str(mochi_bare),
        ],
        tmp_path,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "cannot fast-forward" in combined
    assert "Installing runtime dependencies" not in combined
