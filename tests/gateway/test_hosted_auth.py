from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.hosted import HostedScopeStore, resolve_hosted_context, source_with_hosted_context
from gateway.platforms.base import EphemeralReply, MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource, build_session_key
from gateway.usage import build_hosted_usage_event, record_hosted_usage_event


def _slack_source(*, user_id: str = "U_ADMIN", chat_id: str = "C456") -> SessionSource:
    return SessionSource(
        platform=Platform.SLACK,
        chat_id=chat_id,
        chat_name="sales",
        chat_type="channel",
        user_id=user_id,
        guild_id="T123",
    )


def _event(text: str, source: SessionSource) -> MessageEvent:
    return MessageEvent(text=text, message_type=MessageType.TEXT, source=source)


def _runner(state_root: Path) -> GatewayRunner:
    config = GatewayConfig(
        hosted_mode=True,
        hosted_state_dir=state_root,
        platforms={
            Platform.SLACK: PlatformConfig(
                enabled=True,
                extra={
                    "group_allow_admin_from": ["U_ADMIN"],
                    "group_user_allowed_commands": ["status"],
                },
            )
        },
    )
    return GatewayRunner(config)


def test_slack_workspace_scope_is_shared_and_sender_is_not_part_of_session_key(tmp_path: Path) -> None:
    state_root = tmp_path / "hosted"
    first = source_with_hosted_context(
        _slack_source(user_id="U1"),
        resolve_hosted_context(_slack_source(user_id="U1"), state_root=state_root),
    )
    second = source_with_hosted_context(
        _slack_source(user_id="U2"),
        resolve_hosted_context(_slack_source(user_id="U2"), state_root=state_root),
    )

    assert first.hosted_scope_id == "slack:T123"
    assert second.hosted_scope_id == "slack:T123"
    assert build_session_key(first) == build_session_key(second)


def test_slack_channel_override_switches_only_that_channel(tmp_path: Path) -> None:
    state_root = tmp_path / "hosted"
    store = HostedScopeStore(state_root)
    store.set_channel_override(_slack_source(chat_id="C456"))

    overridden = source_with_hosted_context(
        _slack_source(chat_id="C456"),
        resolve_hosted_context(_slack_source(chat_id="C456"), state_root=state_root),
    )
    other_channel = source_with_hosted_context(
        _slack_source(chat_id="C999"),
        resolve_hosted_context(_slack_source(chat_id="C999"), state_root=state_root),
    )

    assert overridden.hosted_scope_id == "slack:T123:C456"
    assert overridden.hosted_using_channel_override is True
    assert other_channel.hosted_scope_id == "slack:T123"
    assert other_channel.hosted_using_channel_override is False


@pytest.mark.asyncio
async def test_auth_channel_and_workspace_are_ephemeral_control_plane_commands(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "hosted")
    source = _slack_source()

    channel_result = await runner._handle_auth_command(_event("/auth channel", source))
    assert isinstance(channel_result, EphemeralReply)
    assert "channel-specific hosted scope" in channel_result
    assert "`slack:T123:C456`" in channel_result

    workspace_result = await runner._handle_auth_command(_event("/auth workspace", source))
    assert isinstance(workspace_result, EphemeralReply)
    assert "workspace default hosted scope" in workspace_result
    assert "`slack:T123`" in workspace_result


@pytest.mark.asyncio
async def test_auth_status_is_user_allowed_but_group_claim_and_override_are_admin_only(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "hosted")
    runner._claim_hosted_scope_via_growth_mcp = lambda source, email: {
        "claim_token": "00000000-0000-4000-8000-000000000001",
        "message": f"Magic link sent to {email}",
    }
    user_source = _slack_source(user_id="U_USER")

    status_result = await runner._handle_auth_command(_event("/auth status", user_source))
    assert "Mochi auth" in status_result
    assert "Scope: `slack:T123`" in status_result

    claim_result = await runner._handle_auth_command(_event("/auth claim user@example.com", user_source))
    assert "admin-only" in claim_result

    denied = await runner._handle_auth_command(_event("/auth channel", user_source))
    assert "admin-only" in denied


@pytest.mark.asyncio
async def test_auth_claim_is_allowed_in_dm_context(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "hosted")
    runner._issue_hosted_scope_assertion_via_bridge = lambda source: True
    runner._claim_hosted_scope_via_growth_mcp = lambda source, email: {
        "claim_token": "00000000-0000-4000-8000-000000000001",
        "message": f"Magic link sent to {email}",
    }
    dm_source = _slack_source(user_id="U_USER", chat_id="D123")
    dm_source = dataclasses.replace(dm_source, chat_type="dm")

    claim_result = await runner._handle_auth_command(_event("/auth claim user@example.com", dm_source))

    assert isinstance(claim_result, EphemeralReply)
    assert "Magic link sent to user@example.com" in claim_result
    assert "00000000-0000-4000-8000-000000000001" in claim_result


@pytest.mark.asyncio
async def test_auth_claim_does_not_mint_fake_local_tokens_without_growth_mcp(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "hosted")

    source = _slack_source(user_id="U_USER", chat_id="D123")
    source = dataclasses.replace(source, chat_type="dm")
    result = await runner._handle_auth_command(_event("/auth claim", source))

    assert isinstance(result, EphemeralReply)
    assert "hosted-scope assertion" in result


@pytest.mark.asyncio
async def test_auth_claim_uses_growth_mcp_oauth_claim_url(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "hosted")
    runner._issue_hosted_scope_assertion_via_bridge = lambda source: True
    runner._claim_hosted_scope_via_growth_mcp = lambda source, email: {
        "claim_token": "00000000-0000-4000-8000-000000000002",
        "claim_url": "https://platform.local/claim?token=00000000-0000-4000-8000-000000000002",
    }

    source = _slack_source(user_id="U_USER", chat_id="D123")
    source = dataclasses.replace(source, chat_type="dm")
    result = await runner._handle_auth_command(_event("/auth claim", source))

    assert isinstance(result, EphemeralReply)
    assert "Open this claim URL" in result
    assert "https://platform.local/claim" in result


@pytest.mark.asyncio
async def test_auth_use_does_not_persist_workspace_without_growth_mcp_membership(tmp_path: Path) -> None:
    state_root = tmp_path / "hosted"
    runner = _runner(state_root)
    runner._persist_hosted_workspace_selection_via_bridge = lambda source, org_ref, org_slug: {
        "hosted_scope_id": "slack:T123",
        "scope_kind": "workspace",
        "platform": "slack",
        "platform_workspace_id": "T123",
        "platform_channel_id": "C456",
        "platform_conversation_id": "slack:T123:C456",
        "growth_auth_user_id": None,
        "claimed_user_id": "00000000-0000-4000-8000-000000000204",
        "selected_org_id": "00000000-0000-4000-8000-000000000101",
        "selected_org_slug": "acme",
        "claim_token_id": None,
        "scope_status": "active",
        "reset_to_hosted_scope_id": None,
        "scope_key": "slack:T123",
        "last_used_at": "2026-01-01T00:00:00+00:00",
        "metadata": {},
    }
    source = _slack_source()

    result = await runner._handle_auth_command(_event("/auth use acme", source))

    assert isinstance(result, EphemeralReply)
    assert "Workspace selection is unavailable" in result
    resolved = resolve_hosted_context(source, state_root=state_root)
    assert resolved.selected_org_id is None
    assert resolved.selected_org_slug is None


@pytest.mark.asyncio
async def test_auth_use_selects_workspace_through_scoped_growth_mcp(tmp_path: Path) -> None:
    from tools.registry import registry

    state_root = tmp_path / "hosted"
    runner = _runner(state_root)
    source = _slack_source()
    seen: dict[str, object] = {}

    def _handler(args: dict, **_kwargs: object) -> str:
        from gateway.session_context import get_session_env

        seen["args"] = args
        seen["scope"] = get_session_env("HERMES_GATEWAY_AUTH_SCOPE", "")
        return '{"result": {"org_slug": "acme"}}'

    registry.register(
        name="mcp_growth_growth_ensure_workspace",
        toolset="mcp-growth",
        schema={"name": "mcp_growth_growth_ensure_workspace", "parameters": {"type": "object"}},
        handler=_handler,
    )
    try:
        result = await runner._handle_auth_command(_event("/auth use acme", source))
    finally:
        registry.deregister("mcp_growth_growth_ensure_workspace")

    assert isinstance(result, EphemeralReply)
    assert "Selected workspace" in result
    assert seen["args"] == {"workspace_id": "acme"}
    assert seen["scope"] == "slack:T123"
    resolved = resolve_hosted_context(source, state_root=state_root)
    assert resolved.selected_org_slug == "acme"


@pytest.mark.asyncio
async def test_auth_workspaces_syncs_completed_growth_claim(tmp_path: Path) -> None:
    from tools.registry import registry

    state_root = tmp_path / "hosted"
    runner = _runner(state_root)
    source = _slack_source(user_id="U_USER")
    HostedScopeStore(state_root).set_claim_token(
        source,
        "00000000-0000-4000-8000-000000000004",
    )
    def _handler(_args: dict, **_kwargs: object) -> str:
        return (
            '{"result": {"status": "claimed", '
            '"claimed_user_id": "00000000-0000-4000-8000-000000000204", '
            '"hosted_scope_id": "slack:T123", '
            '"hosted_scope_claim_projected": true}}'
        )

    registry.register(
        name="mcp_growth_growth_check_claim_status",
        toolset="mcp-growth",
        schema={"name": "mcp_growth_growth_check_claim_status", "parameters": {"type": "object"}},
        handler=_handler,
    )
    try:
        result = await runner._handle_auth_command(_event("/auth workspaces", source))
    finally:
        registry.deregister("mcp_growth_growth_check_claim_status")

    assert isinstance(result, EphemeralReply)
    assert "No workspace is selected yet" in result
    resolved = resolve_hosted_context(source, state_root=state_root)
    assert resolved.claim_status == "claimed"


@pytest.mark.asyncio
async def test_auth_workspaces_does_not_mark_claimed_without_backend_projection(tmp_path: Path) -> None:
    from tools.registry import registry

    state_root = tmp_path / "hosted"
    runner = _runner(state_root)
    source = _slack_source(user_id="U_USER")
    HostedScopeStore(state_root).set_claim_token(
        source,
        "00000000-0000-4000-8000-000000000004",
    )

    def _handler(_args: dict, **_kwargs: object) -> str:
        return (
            '{"result": {"status": "claimed", '
            '"claimed_user_id": "00000000-0000-4000-8000-000000000204"}}'
        )

    registry.register(
        name="mcp_growth_growth_check_claim_status",
        toolset="mcp-growth",
        schema={"name": "mcp_growth_growth_check_claim_status", "parameters": {"type": "object"}},
        handler=_handler,
    )
    try:
        result = await runner._handle_auth_command(_event("/auth workspaces", source))
    finally:
        registry.deregister("mcp_growth_growth_check_claim_status")

    assert isinstance(result, EphemeralReply)
    assert "anonymous" in result
    resolved = resolve_hosted_context(source, state_root=state_root)
    assert resolved.claim_status == "anonymous"


@pytest.mark.asyncio
async def test_unknown_auth_subcommand_returns_usage(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "hosted")

    result = await runner._handle_auth_command(_event("/auth nonsense", _slack_source()))

    assert "Unknown /auth subcommand" in result
    assert "/auth status" in result


def test_mochi_test_homes_are_isolated_from_real_agent_state() -> None:
    for env_name in (
        "HOME",
        "HERMES_HOME",
        "CODEX_HOME",
        "CLAUDE_HOME",
        "CLAUDE_CONFIG_DIR",
        "GROWTH_MCP_AUTH_DIR",
        "GROWTH_MCP_BROWSER_PROFILE_DIR",
        "MOCHI_HOSTED_STATE_ROOT",
    ):
        raw = os.environ.get(env_name)
        assert raw, f"{env_name} must be isolated in tests"
        assert Path(raw).exists()


def test_growth_mcp_claim_helper_injects_scope_local_env(tmp_path: Path) -> None:
    from gateway.session_context import get_session_env
    from tools.registry import registry

    state_root = tmp_path / "hosted"
    runner = _runner(state_root)
    HostedScopeStore(state_root).apply_backend_scope(
        _slack_source(user_id="U_USER"),
        {
            "hosted_scope_id": "slack:T123",
            "scope_kind": "workspace",
            "platform": "slack",
            "platform_workspace_id": "T123",
            "platform_channel_id": "C456",
            "platform_conversation_id": "slack:T123:C456",
            "claim_assertion": "assertion-secret",
            "scope_key": "slack:T123",
            "last_used_at": "2026-01-01T00:00:00+00:00",
            "metadata": {},
        },
    )
    source = source_with_hosted_context(
        _slack_source(user_id="U_USER"),
        resolve_hosted_context(_slack_source(user_id="U_USER"), state_root=state_root),
    )
    seen: dict[str, str] = {}

    def _handler(_args: dict, **_kwargs: object) -> str:
        seen["scope"] = get_session_env("HERMES_GATEWAY_AUTH_SCOPE", "")
        seen["auth_root"] = get_session_env("MOCHI_HOSTED_GATEWAY_AUTH_ROOT", "")
        seen["assertion"] = get_session_env("MOCHI_HOSTED_SCOPE_ASSERTION", "")
        return (
            '{"result": {"claim_token": "00000000-0000-4000-8000-000000000003", '
            '"message": "Magic link sent"}}'
        )

    registry.register(
        name="mcp_growth_growth_claim_account",
        toolset="mcp-growth",
        schema={"name": "mcp_growth_growth_claim_account", "parameters": {"type": "object"}},
        handler=_handler,
    )
    try:
        result = runner._claim_hosted_scope_via_growth_mcp(source, email="user@example.com")
    finally:
        registry.deregister("mcp_growth_growth_claim_account")

    assert result is not None
    assert result["claim_token"] == "00000000-0000-4000-8000-000000000003"
    assert seen["scope"] == "slack:T123"
    assert seen["auth_root"] == str(state_root / "state" / "slack_T123" / "auth")
    assert seen["assertion"] == "assertion-secret"


def test_hosted_usage_event_contains_billing_ready_scope_and_idempotency(tmp_path: Path) -> None:
    source = source_with_hosted_context(
        _slack_source(user_id="U_USAGE"),
        resolve_hosted_context(_slack_source(user_id="U_USAGE"), state_root=tmp_path / "hosted"),
    )
    event = _event("hello", source)
    event.message_id = "m-123"

    payload = build_hosted_usage_event(
        event=event,
        source=source,
        session_id="sess-1",
        session_key="agent:hosted:slack:T123",
        agent_result={
            "provider": "openai",
            "model": "gpt-test",
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_tokens": 2,
            "reasoning_tokens": 1,
            "total_tokens": 18,
            "estimated_cost_usd": 0.001,
            "api_calls": 1,
        },
    )

    assert payload is not None
    assert payload["hosted_scope_id"] == "slack:T123"
    assert payload["conversation_scope_id"] == "slack:T123:C456"
    assert payload["idempotency_key"] == "mochi:slack:T123:slack:T123:C456:sess-1:m-123:1:18"
    assert payload["event_type"] == "llm_tokens"
    assert "billing_status" not in payload
    assert "pricing_version" not in payload


def test_hosted_usage_append_uses_configured_state_root(tmp_path: Path) -> None:
    state_root = tmp_path / "configured-hosted"
    source = source_with_hosted_context(
        _slack_source(user_id="U_USAGE"),
        resolve_hosted_context(_slack_source(user_id="U_USAGE"), state_root=state_root),
    )
    event = _event("hello", source)
    event.message_id = "m-456"

    record_hosted_usage_event(
        event=event,
        source=source,
        session_id="sess-2",
        session_key="agent:hosted:slack:T123",
        agent_result={"total_tokens": 3, "api_calls": 1},
        state_root=state_root,
    )

    assert (state_root / "usage-events.jsonl").exists()
