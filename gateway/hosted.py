"""Hosted multi-tenant scope resolution for Mochi gateway messages.

This module is intentionally small and file-backed. The bridge/backend owns the
durable hosted identity in production, but the gateway still needs a fast local
projection so session routing, browser auth, Growth MCP auth, and slash command
state can be resolved before an agent run starts.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from utils import atomic_replace

from .config import Platform
from .session import SessionSource, _hash_sender_id, resolve_gateway_auth_scope


HOSTED_STATE_ENV = "MOCHI_HOSTED_STATE_ROOT"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _component(value: object) -> str:
    raw = str(value or "").strip()
    return raw.replace("/", "_").replace("\\", "_").replace(":", "_")


def _scope_id(*parts: object) -> str:
    return ":".join(_component(p) for p in parts if _component(p))


def default_hosted_state_root() -> Path:
    raw = os.environ.get(HOSTED_STATE_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    raw_home = os.environ.get("HERMES_HOME", "").strip()
    if raw_home:
        return Path(raw_home).expanduser() / "hosted"
    raise RuntimeError("Hosted Mochi requires MOCHI_HOSTED_STATE_ROOT or HERMES_HOME.")


def _platform_workspace_id(source: SessionSource) -> str:
    if source.platform == Platform.SLACK:
        return source.guild_id or ""
    return source.guild_id or source.chat_id_alt or source.chat_id or ""


def _platform_channel_id(source: SessionSource) -> str:
    if source.platform == Platform.SLACK:
        return source.chat_id or ""
    if source.chat_type == "group":
        return source.chat_id_alt or source.chat_id or ""
    return source.chat_id or ""


def conversation_scope_id(source: SessionSource) -> str:
    base = _scope_id(source.platform.value, _platform_workspace_id(source), _platform_channel_id(source))
    if source.thread_id:
        return _scope_id(base, source.thread_id)
    return base or _scope_id(source.platform.value, source.chat_id, source.thread_id)


def workspace_scope_id(source: SessionSource) -> str:
    if source.platform == Platform.SLACK:
        workspace = _platform_workspace_id(source)
        return _scope_id("slack", workspace) if workspace else _scope_id("slack", source.chat_id)

    auth_scope = resolve_gateway_auth_scope(source)
    if auth_scope:
        return auth_scope
    return _scope_id(source.platform.value, _platform_workspace_id(source), _platform_channel_id(source))


def channel_scope_id(source: SessionSource) -> str:
    if source.platform == Platform.SLACK:
        workspace = _platform_workspace_id(source)
        channel = _platform_channel_id(source)
        return _scope_id("slack", workspace, channel) if workspace and channel else workspace_scope_id(source)
    return workspace_scope_id(source)


def channel_override_key(source: SessionSource) -> str:
    return channel_scope_id(source)


def fresh_channel_scope_id(source: SessionSource) -> str:
    return _scope_id(channel_scope_id(source), "anon", uuid.uuid4().hex[:12])


@dataclass(frozen=True)
class HostedScopeRecord:
    hosted_scope_id: str
    scope_kind: str
    platform: str
    platform_workspace_id: str = ""
    platform_channel_id: str = ""
    platform_conversation_id: str = ""
    growth_auth_user_id: Optional[str] = None
    claimed_user_id: Optional[str] = None
    selected_org_id: Optional[str] = None
    selected_org_slug: Optional[str] = None
    claim_token_id: Optional[str] = None
    scope_key: Optional[str] = None
    claim_assertion: Optional[str] = None
    claim_assertion_expires_at: Optional[str] = None
    created_at: str = ""
    claimed_at: Optional[str] = None
    last_used_at: str = ""
    metadata: dict[str, Any] | None = None

    @property
    def claim_status(self) -> str:
        return "claimed" if self.claimed_user_id else "anonymous"


@dataclass(frozen=True)
class HostedExecutionContext:
    hosted_scope_id: str
    conversation_scope_id: str
    scope_kind: str
    platform: str
    platform_workspace_id: str
    platform_channel_id: str
    platform_thread_id: str
    platform_sender_id: str
    platform_sender_hash: str
    state_root: Path
    filesystem_root: Path
    browser_profile_root: Path
    growth_auth_root: Path
    memory_root: Path
    skills_root: Path
    sessions_root: Path
    claim_status: str
    selected_org_id: Optional[str]
    selected_org_slug: Optional[str]
    scope_assertion: Optional[str]
    using_channel_override: bool


class HostedScopeStore:
    def __init__(self, state_root: Path | None = None) -> None:
        self.state_root = state_root or default_hosted_state_root()
        self.path = self.state_root / "scopes.json"

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(".lock")
        with lock_path.open("a+", encoding="utf-8") as handle:
            try:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass
            try:
                yield
            finally:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"scopes": {}, "overrides": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"scopes": {}, "overrides": {}}
        if not isinstance(data, dict):
            return {"scopes": {}, "overrides": {}}
        scopes = data.get("scopes")
        overrides = data.get("overrides")
        return {
            "scopes": scopes if isinstance(scopes, dict) else {},
            "overrides": overrides if isinstance(overrides, dict) else {},
        }

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        atomic_replace(str(tmp), str(self.path))

    def _record_from_source(self, source: SessionSource, hosted_scope_id: str, scope_kind: str) -> HostedScopeRecord:
        now = _now_iso()
        return HostedScopeRecord(
            hosted_scope_id=hosted_scope_id,
            scope_kind=scope_kind,
            platform=source.platform.value,
            platform_workspace_id=_platform_workspace_id(source),
            platform_channel_id=_platform_channel_id(source),
            platform_conversation_id=conversation_scope_id(source),
            created_at=now,
            last_used_at=now,
            metadata={},
        )

    def get_or_create_scope(
        self,
        source: SessionSource,
        *,
        scope_kind: str = "workspace",
        force_scope_id: str | None = None,
    ) -> HostedScopeRecord:
        hosted_scope_id = force_scope_id or (
            channel_scope_id(source) if scope_kind == "channel" else workspace_scope_id(source)
        )
        with self._locked():
            data = self._load()
            scopes = data["scopes"]
            raw = scopes.get(hosted_scope_id)
            if isinstance(raw, dict):
                record = HostedScopeRecord(**raw)
            else:
                record = self._record_from_source(source, hosted_scope_id, scope_kind)
            record = replace(record, last_used_at=_now_iso())
            scopes[hosted_scope_id] = asdict(record)
            self._save(data)
            return record

    def set_channel_override(self, source: SessionSource) -> HostedScopeRecord:
        record = self.get_or_create_scope(source, scope_kind="channel", force_scope_id=channel_scope_id(source))
        with self._locked():
            data = self._load()
            data["overrides"][channel_override_key(source)] = record.hosted_scope_id
            data["scopes"][record.hosted_scope_id] = asdict(record)
            self._save(data)
            return record

    def clear_channel_override(self, source: SessionSource) -> None:
        with self._locked():
            data = self._load()
            data["overrides"].pop(channel_override_key(source), None)
            self._save(data)

    def reset_channel_override(self, source: SessionSource) -> HostedScopeRecord:
        hosted_scope_id = fresh_channel_scope_id(source)
        record = self._record_from_source(source, hosted_scope_id, "channel")
        with self._locked():
            data = self._load()
            data["overrides"][channel_override_key(source)] = record.hosted_scope_id
            data["scopes"][record.hosted_scope_id] = asdict(record)
            self._save(data)
            return record

    def current_scope(self, source: SessionSource) -> tuple[HostedScopeRecord, bool]:
        data = self._load()
        override_id = data["overrides"].get(channel_override_key(source))
        if isinstance(override_id, str) and override_id:
            return self.get_or_create_scope(source, scope_kind="channel", force_scope_id=override_id), True
        return self.get_or_create_scope(source, scope_kind="workspace"), False

    def set_claim_token(self, source: SessionSource, token: str) -> HostedScopeRecord:
        record, _ = self.current_scope(source)
        with self._locked():
            data = self._load()
            next_record = replace(record, claim_token_id=token, last_used_at=_now_iso())
            data["scopes"][next_record.hosted_scope_id] = asdict(next_record)
            self._save(data)
            return next_record

    def mark_claimed(
        self,
        source: SessionSource,
        *,
        claimed_user_id: str,
        claim_token_id: str | None = None,
    ) -> HostedScopeRecord:
        record, _ = self.current_scope(source)
        with self._locked():
            data = self._load()
            next_record = replace(
                record,
                claimed_user_id=claimed_user_id,
                claim_token_id=claim_token_id or record.claim_token_id,
                claimed_at=record.claimed_at or _now_iso(),
                last_used_at=_now_iso(),
            )
            data["scopes"][next_record.hosted_scope_id] = asdict(next_record)
            self._save(data)
            return next_record

    def select_workspace(self, source: SessionSource, org_ref: str) -> HostedScopeRecord:
        record, _ = self.current_scope(source)
        with self._locked():
            data = self._load()
            selected_org_id = org_ref if "-" in org_ref else record.selected_org_id
            selected_org_slug = org_ref if "-" not in org_ref else record.selected_org_slug
            next_record = replace(
                record,
                selected_org_id=selected_org_id,
                selected_org_slug=selected_org_slug,
                last_used_at=_now_iso(),
            )
            data["scopes"][next_record.hosted_scope_id] = asdict(next_record)
            self._save(data)
            return next_record

    def apply_backend_scope(self, source: SessionSource, payload: dict[str, Any]) -> HostedScopeRecord:
        hosted_scope_id = str(payload.get("hosted_scope_id") or "")
        if not hosted_scope_id:
            raise ValueError("backend hosted scope response did not include hosted_scope_id")
        with self._locked():
            data = self._load()
            current_raw = data["scopes"].get(hosted_scope_id)
            current = (
                HostedScopeRecord(**current_raw)
                if isinstance(current_raw, dict)
                else self._record_from_source(source, hosted_scope_id, str(payload.get("scope_kind") or "workspace"))
            )
            next_record = replace(
                current,
                hosted_scope_id=hosted_scope_id,
                scope_kind=str(payload.get("scope_kind") or current.scope_kind),
                platform=str(payload.get("platform") or current.platform),
                platform_workspace_id=str(payload.get("platform_workspace_id") or current.platform_workspace_id or ""),
                platform_channel_id=str(payload.get("platform_channel_id") or current.platform_channel_id or ""),
                platform_conversation_id=str(payload.get("platform_conversation_id") or current.platform_conversation_id or ""),
                growth_auth_user_id=payload.get("growth_auth_user_id") or current.growth_auth_user_id,
                claimed_user_id=payload.get("claimed_user_id") or current.claimed_user_id,
                selected_org_id=payload.get("selected_org_id") or current.selected_org_id,
                selected_org_slug=payload.get("selected_org_slug") or current.selected_org_slug,
                claim_token_id=payload.get("claim_token_id") or current.claim_token_id,
                scope_key=payload.get("scope_key") or current.scope_key,
                claim_assertion=payload.get("claim_assertion") or current.claim_assertion,
                claim_assertion_expires_at=payload.get("claim_assertion_expires_at") or current.claim_assertion_expires_at,
                claimed_at=payload.get("claimed_at") or current.claimed_at,
                last_used_at=payload.get("last_used_at") or _now_iso(),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else current.metadata,
            )
            data["scopes"][hosted_scope_id] = asdict(next_record)
            if next_record.scope_kind == "channel" and hosted_scope_id != channel_scope_id(source):
                data["overrides"][channel_override_key(source)] = hosted_scope_id
            self._save(data)
            return next_record


def resolve_hosted_context(source: SessionSource, *, state_root: Path | None = None) -> HostedExecutionContext:
    store = HostedScopeStore(state_root)
    record, using_override = store.current_scope(source)
    scope_root = store.state_root / "state" / _component(record.hosted_scope_id)
    conv_id = conversation_scope_id(source)
    sender_id = str(source.user_id_alt or source.user_id or "")
    return HostedExecutionContext(
        hosted_scope_id=record.hosted_scope_id,
        conversation_scope_id=conv_id,
        scope_kind=record.scope_kind,
        platform=source.platform.value,
        platform_workspace_id=_platform_workspace_id(source),
        platform_channel_id=_platform_channel_id(source),
        platform_thread_id=str(source.thread_id or ""),
        platform_sender_id=sender_id,
        platform_sender_hash=_hash_sender_id(sender_id) if sender_id else "",
        state_root=scope_root,
        filesystem_root=scope_root / "conversations" / _component(conv_id) / "files",
        browser_profile_root=scope_root / "browser",
        growth_auth_root=scope_root / "auth",
        memory_root=scope_root / "memory",
        skills_root=scope_root / "skills",
        sessions_root=scope_root / "sessions",
        claim_status=record.claim_status,
        selected_org_id=record.selected_org_id,
        selected_org_slug=record.selected_org_slug,
        scope_assertion=record.claim_assertion,
        using_channel_override=using_override,
    )


def source_with_hosted_context(source: SessionSource, context: HostedExecutionContext) -> SessionSource:
    return replace(
        source,
        hosted_scope_id=context.hosted_scope_id,
        conversation_scope_id=context.conversation_scope_id,
        hosted_scope_kind=context.scope_kind,
        hosted_claim_status=context.claim_status,
        hosted_selected_org_id=context.selected_org_id,
        hosted_selected_org_slug=context.selected_org_slug,
        hosted_using_channel_override=context.using_channel_override,
    )
