"""Hosted Mochi usage event emission.

Usage accounting is intentionally best-effort in the gateway. The backend
ledger is the billing-grade source of truth; gateway write failures must never
fail an agent turn.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .hosted import default_hosted_state_root
from .platforms.base import MessageEvent
from .session import SessionSource, _hash_sender_id

logger = logging.getLogger(__name__)


def _event_text_hash(event: MessageEvent) -> str:
    text = event.text or ""
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def build_hosted_usage_event(
    *,
    event: MessageEvent,
    source: SessionSource,
    session_id: str,
    session_key: str,
    agent_result: dict[str, Any],
) -> dict[str, Any] | None:
    if not source.hosted_scope_id:
        return None
    total_tokens = int(agent_result.get("total_tokens", 0) or 0)
    api_calls = int(agent_result.get("api_calls", 0) or 0)
    estimated_cost = agent_result.get("estimated_cost_usd")
    if total_tokens <= 0 and api_calls <= 0 and not estimated_cost:
        return None

    msg_id = event.message_id or source.message_id or _event_text_hash(event)
    idempotency_key = (
        f"mochi:{source.hosted_scope_id}:{source.conversation_scope_id or source.chat_id}:"
        f"{session_id}:{msg_id}:{api_calls}:{total_tokens}"
    )
    occurred_at = datetime.now(timezone.utc).isoformat()
    return {
        "idempotency_key": idempotency_key,
        "hosted_scope_id": source.hosted_scope_id,
        "conversation_scope_id": source.conversation_scope_id,
        "session_id": session_id,
        "run_id": session_key,
        "platform": source.platform.value if source.platform else "",
        "platform_sender_hash": _hash_sender_id(str(source.user_id_alt or source.user_id or "")),
        "event_type": "llm_tokens",
        "usage_family": "llm",
        "usage_unit": "token",
        "provider": agent_result.get("provider"),
        "model": agent_result.get("model"),
        "input_tokens": int(agent_result.get("input_tokens", 0) or 0),
        "output_tokens": int(agent_result.get("output_tokens", 0) or 0),
        "cached_input_tokens": int(agent_result.get("cache_read_tokens", 0) or 0),
        "reasoning_tokens": int(agent_result.get("reasoning_tokens", 0) or 0),
        "total_tokens": total_tokens,
        "occurred_at": occurred_at,
        "metadata": {
            "session_key": session_key,
            "api_calls": api_calls,
            "estimated_cost_usd": estimated_cost,
            "cost_status": agent_result.get("cost_status"),
            "cost_source": agent_result.get("cost_source"),
        },
    }


def _append_local_usage_event(payload: dict[str, Any], *, state_root: Path | None) -> None:
    root = state_root or default_hosted_state_root()
    path = root / "usage-events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _post_usage_event(payload: dict[str, Any]) -> None:
    base_url = os.getenv("MOCHI_BRIDGE_BASE_URL", "").strip().rstrip("/")
    token = (
        os.getenv("MOCHI_BRIDGE_INTERNAL_TOKEN", "").strip()
        or os.getenv("INTERNAL_SERVICE_TOKEN", "").strip()
    )
    if not base_url or not token:
        return
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/hosted-agent/usage-events",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-internal-token": token,
        },
    )
    with urllib.request.urlopen(request, timeout=1.0) as response:
        response.read()


def record_hosted_usage_event(
    *,
    event: MessageEvent,
    source: SessionSource,
    session_id: str,
    session_key: str,
    agent_result: dict[str, Any],
    state_root: Path | None,
) -> None:
    payload = build_hosted_usage_event(
        event=event,
        source=source,
        session_id=session_id,
        session_key=session_key,
        agent_result=agent_result,
    )
    if payload is None:
        return
    try:
        _append_local_usage_event(payload, state_root=state_root)
    except Exception:
        logger.warning("Failed to append hosted Mochi usage event", exc_info=True)
    try:
        _post_usage_event(payload)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        logger.warning("Failed to post hosted Mochi usage event", exc_info=True)
    except Exception:
        logger.warning("Unexpected hosted Mochi usage write failure", exc_info=True)
