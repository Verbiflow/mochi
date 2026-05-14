#!/usr/bin/env bash
# Migrate an existing Hermes git install to the Mochi fork without deleting
# ~/.hermes state. Intended for Mac mini gateway hosts, but works on Linux too.

set -euo pipefail

DEFAULT_REPO_URL="https://github.com/Verbiflow/mochi.git"
DEFAULT_BRANCH="main"

REPO_URL="${MOCHI_REPO_URL:-$DEFAULT_REPO_URL}"
BRANCH="${MOCHI_BRANCH:-$DEFAULT_BRANCH}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
INSTALL_DIR="${HERMES_INSTALL_DIR:-}"
INSTALL_DIR_EXPLICIT=false

usage() {
    cat <<EOF
Usage: migrate_to_mochi.sh [OPTIONS]

Options:
  --repo-url URL       Mochi repository URL (default: $DEFAULT_REPO_URL)
  --branch NAME        Branch to migrate to (default: main)
  --install-dir PATH   Existing Hermes checkout (default: auto-detect)
  --hermes-home PATH   Data directory (default: ~/.hermes)
  -h, --help           Show this help

Environment:
  MOCHI_REPO_URL       Default repository URL override
  HERMES_INSTALL_DIR   Existing checkout override
  HERMES_HOME          Data directory override
EOF
}

log() {
    printf '%s\n' "$*"
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

expand_path() {
    case "$1" in
        "~") printf '%s\n' "$HOME" ;;
        "~/"*) printf '%s/%s\n' "$HOME" "${1#~/}" ;;
        *) printf '%s\n' "$1" ;;
    esac
}

resolve_path() {
    local path="$1"
    local dir
    local base
    local target

    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        return 1
    fi

    while [ -L "$path" ]; do
        dir="$(cd "$(dirname "$path")" && pwd -P)"
        target="$(readlink "$path")"
        case "$target" in
            /*) path="$target" ;;
            *) path="$dir/$target" ;;
        esac
    done

    dir="$(cd "$(dirname "$path")" && pwd -P)"
    base="$(basename "$path")"
    printf '%s/%s\n' "$dir" "$base"
}

normalize_remote() {
    local url="${1:-}"
    url="${url%/}"
    url="${url%.git}"
    printf '%s\n' "$url"
}

is_legacy_hermes_remote() {
    local normalized
    normalized="$(normalize_remote "${1:-}")"
    case "$normalized" in
        "https://github.com/NousResearch/hermes-agent"|"git@github.com:NousResearch/hermes-agent")
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --repo-url)
                [ "$#" -ge 2 ] || die "--repo-url requires a value"
                REPO_URL="$2"
                shift 2
                ;;
            --branch)
                [ "$#" -ge 2 ] || die "--branch requires a value"
                BRANCH="$2"
                shift 2
                ;;
            --install-dir)
                [ "$#" -ge 2 ] || die "--install-dir requires a value"
                INSTALL_DIR="$(expand_path "$2")"
                INSTALL_DIR_EXPLICIT=true
                shift 2
                ;;
            --hermes-home)
                [ "$#" -ge 2 ] || die "--hermes-home requires a value"
                HERMES_HOME="$(expand_path "$2")"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "unknown option: $1"
                ;;
        esac
    done
}

repo_from_hermes_command() {
    local hermes_bin
    local resolved
    local candidate

    hermes_bin="$(command -v hermes 2>/dev/null || true)"
    [ -n "$hermes_bin" ] || return 1

    resolved="$(resolve_path "$hermes_bin" 2>/dev/null || true)"
    [ -n "$resolved" ] || return 1

    candidate="$(cd "$(dirname "$resolved")/../.." 2>/dev/null && pwd -P || true)"
    if [ -n "$candidate" ] && [ -f "$candidate/pyproject.toml" ]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    candidate="$(cd "$(dirname "$resolved")/../../.." 2>/dev/null && pwd -P || true)"
    if [ -n "$candidate" ] && [ -f "$candidate/pyproject.toml" ]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    return 1
}

detect_install_dir() {
    local candidate

    if [ "$INSTALL_DIR_EXPLICIT" = true ] && [ -n "$INSTALL_DIR" ]; then
        printf '%s\n' "$INSTALL_DIR"
        return 0
    fi

    if [ -n "${HERMES_INSTALL_DIR:-}" ]; then
        printf '%s\n' "$(expand_path "$HERMES_INSTALL_DIR")"
        return 0
    fi

    candidate="$(repo_from_hermes_command 2>/dev/null || true)"
    if [ -n "$candidate" ]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    candidate="$HERMES_HOME/hermes-agent"
    if [ -d "$candidate/.git" ]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    candidate="/usr/local/lib/hermes-agent"
    if [ -d "$candidate/.git" ]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    return 1
}

verify_checkout() {
    [ -d "$INSTALL_DIR/.git" ] || die "$INSTALL_DIR is not a git checkout"
    [ -f "$INSTALL_DIR/pyproject.toml" ] || die "$INSTALL_DIR is missing pyproject.toml"
    if ! grep -Eq 'name[[:space:]]*=[[:space:]]*"(hermes-agent|mochi)"' "$INSTALL_DIR/pyproject.toml"; then
        die "$INSTALL_DIR does not look like a Hermes/Mochi checkout"
    fi
}

create_backup() {
    local timestamp
    timestamp="$(date -u +%Y%m%d-%H%M%S)"
    BACKUP_DIR="$HERMES_HOME/backups/mochi-migration-$timestamp"
    mkdir -p "$BACKUP_DIR"

    (
        cd "$INSTALL_DIR"
        git remote -v > "$BACKUP_DIR/git-remotes.txt" 2>&1 || true
        git status --short --branch > "$BACKUP_DIR/git-status.txt" 2>&1 || true
        git rev-parse HEAD > "$BACKUP_DIR/git-head.txt" 2>&1 || true
    )

    if [ -d "$HERMES_HOME" ]; then
        tar -czf "$BACKUP_DIR/hermes-home-state.tar.gz" \
            --exclude './backups' \
            --exclude './hermes-agent' \
            --exclude './node' \
            --exclude './logs' \
            --exclude './cache' \
            --exclude './caches' \
            --exclude './venv' \
            --exclude './.venv' \
            -C "$HERMES_HOME" . 2>/dev/null || true
    fi

    log "Backup: $BACKUP_DIR"
}

gateway_command_available() {
    command -v hermes >/dev/null 2>&1
}

gateway_running() {
    if [ "${MOCHI_MIGRATION_SKIP_GATEWAY:-}" = "1" ]; then
        return 1
    fi

    if gateway_command_available; then
        local out
        out="$(hermes gateway status 2>&1 || true)"
        case "$out" in
            *"Gateway is running"*|*"active (running)"*|*"com.hermes.gateway"*"started"*)
                return 0
                ;;
            *"Gateway is not running"*|*"inactive"*|*"not loaded"*)
                return 1
                ;;
        esac
    fi

    if [ -x "$INSTALL_DIR/venv/bin/python" ]; then
        "$INSTALL_DIR/venv/bin/python" - "$INSTALL_DIR" <<'PY' >/dev/null 2>&1
import sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo))
from gateway.status import get_running_pid

raise SystemExit(0 if get_running_pid() else 1)
PY
        return $?
    fi

    return 1
}

stop_gateway_if_needed() {
    WAS_GATEWAY_RUNNING=false

    if gateway_running; then
        WAS_GATEWAY_RUNNING=true
        gateway_command_available || die "gateway appears to be running, but 'hermes' is not on PATH; stop it manually first"
        log "Stopping gateway..."
        hermes gateway stop
    else
        log "Gateway is not running; it will not be restarted."
    fi
}

configure_remotes() {
    local upstream_url

    log "Setting origin to $REPO_URL"
    git remote set-url origin "$REPO_URL" 2>/dev/null || git remote add origin "$REPO_URL"

    upstream_url="$(git remote get-url upstream 2>/dev/null || true)"
    if [ -n "$upstream_url" ]; then
        if is_legacy_hermes_remote "$upstream_url"; then
            log "Removing legacy upstream remote: $upstream_url"
            git remote remove upstream
        else
            log "Keeping existing non-legacy upstream remote: $upstream_url"
        fi
    fi

    if [ -f "$HERMES_HOME/.skip_upstream_prompt" ]; then
        rm -f "$HERMES_HOME/.skip_upstream_prompt"
        log "Removed legacy upstream prompt marker."
    fi
}

stash_local_changes() {
    STASH_REF=""
    STASH_SELECTOR=""
    if [ -n "$(git status --porcelain)" ]; then
        local stash_name
        stash_name="mochi-migration-autostash-$(date -u +%Y%m%d-%H%M%S)"
        log "Local changes detected; stashing them before migration..."
        git stash push --include-untracked -m "$stash_name"
        STASH_SELECTOR="stash@{0}"
        STASH_REF="$(git rev-parse --verify refs/stash)"
        log "Stash: $STASH_REF"
    fi
}

restore_stashed_changes() {
    if [ -z "${STASH_REF:-}" ]; then
        return
    fi

    log "Restoring stashed local changes..."
    if ! git stash apply "$STASH_REF"; then
        log ""
        log "Migration stopped before dependency install or gateway restart."
        log "Your backup is at: $BACKUP_DIR"
        log "Your local changes are preserved in git stash: $STASH_REF"
        log "Restore later with: git stash apply $STASH_REF"
        git reset --hard HEAD >/dev/null 2>&1 || true
        die "stashed local changes could not be applied cleanly"
    fi

    if git stash drop "${STASH_SELECTOR:-$STASH_REF}" >/dev/null 2>&1; then
        log "Restored local changes and removed migration stash."
        STASH_REF=""
        STASH_SELECTOR=""
    else
        log "Restored local changes, but could not drop stash: $STASH_REF"
        log "Check it later with: git stash list"
    fi
}

checkout_and_fast_forward() {
    log "Fetching $BRANCH from origin..."
    git fetch origin "$BRANCH" --tags

    stash_local_changes

    if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
        git checkout "$BRANCH"
    else
        git checkout -b "$BRANCH" "origin/$BRANCH"
    fi

    log "Fast-forwarding to origin/$BRANCH..."
    if ! git merge --ff-only "origin/$BRANCH"; then
        log ""
        log "Migration stopped before dependency install or gateway restart."
        log "Your backup is at: $BACKUP_DIR"
        if [ -n "$STASH_REF" ]; then
            log "Your local changes are preserved in git stash: $STASH_REF"
            log "Restore later with: git stash apply $STASH_REF"
        fi
        die "local checkout cannot fast-forward to origin/$BRANCH"
    fi

    restore_stashed_changes
}

install_runtime_dependencies() {
    if [ "${MOCHI_MIGRATION_SKIP_DEPS:-}" = "1" ]; then
        log "Skipping dependency install because MOCHI_MIGRATION_SKIP_DEPS=1"
        return
    fi

    local python_bin="$INSTALL_DIR/venv/bin/python"
    [ -x "$python_bin" ] || die "runtime venv not found at $python_bin"
    command -v uv >/dev/null 2>&1 || die "uv is required. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"

    log "Installing runtime dependencies into $INSTALL_DIR/venv..."
    uv pip install --python "$python_bin" -e ".[all,messaging,slack]"
}

restart_gateway_if_needed() {
    if [ "$WAS_GATEWAY_RUNNING" = true ]; then
        gateway_command_available || die "gateway was running before migration, but 'hermes' is not on PATH for restart"
        log "Restarting gateway..."
        hermes gateway restart
    fi
}

print_summary() {
    local commit
    local origin
    commit="$(git rev-parse --short HEAD)"
    origin="$(git remote get-url origin)"

    log ""
    log "Mochi migration complete."
    log "Commit: $commit"
    log "Origin: $origin"
    log "Backup: $BACKUP_DIR"
    if [ -n "${STASH_REF:-}" ]; then
        log "Local changes stash: $STASH_REF"
        log "Restore later with: git stash apply $STASH_REF"
    fi
    log "Next update command: hermes update"
    log ""
    if gateway_command_available; then
        hermes gateway status || true
    else
        log "Gateway status skipped: hermes command not found on PATH."
    fi
}

main() {
    parse_args "$@"

    HERMES_HOME="$(expand_path "$HERMES_HOME")"
    mkdir -p "$HERMES_HOME"

    INSTALL_DIR="$(detect_install_dir)" || die "could not detect Hermes install directory; pass --install-dir"
    INSTALL_DIR="$(expand_path "$INSTALL_DIR")"
    INSTALL_DIR="$(cd "$INSTALL_DIR" && pwd -P)"

    log "Hermes home: $HERMES_HOME"
    log "Install dir: $INSTALL_DIR"
    log "Mochi repo:  $REPO_URL"
    log "Branch:      $BRANCH"

    verify_checkout
    create_backup
    stop_gateway_if_needed

    cd "$INSTALL_DIR"
    configure_remotes
    checkout_and_fast_forward
    install_runtime_dependencies
    restart_gateway_if_needed
    print_summary
}

main "$@"
