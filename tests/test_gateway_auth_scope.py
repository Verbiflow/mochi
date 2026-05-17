from pathlib import Path

from gateway.config import Platform
from gateway.session import SessionSource, resolve_gateway_auth_scope
from gateway.session_context import clear_session_vars, set_session_vars
from tools import mcp_tool
from tools.file_tools import read_file_tool, write_file_tool
from tools.path_security import gateway_auth_path_error, hosted_filesystem_path_error
from tools.terminal_tool import terminal_tool


def test_slack_gateway_auth_scope_is_workspace_level():
    first = SessionSource(
        platform=Platform.SLACK,
        chat_id="C111",
        user_id="U111",
        thread_id="1710000000.1",
        guild_id="T123",
    )
    second = SessionSource(
        platform=Platform.SLACK,
        chat_id="C222",
        user_id="U222",
        thread_id="1710000000.2",
        guild_id="T123",
    )

    assert resolve_gateway_auth_scope(first) == "slack:T123"
    assert resolve_gateway_auth_scope(second) == "slack:T123"


def test_slack_gateway_auth_scope_separates_workspaces():
    assert resolve_gateway_auth_scope(
        SessionSource(platform=Platform.SLACK, chat_id="C1", guild_id="T1")
    ) == "slack:T1"
    assert resolve_gateway_auth_scope(
        SessionSource(platform=Platform.SLACK, chat_id="C1", guild_id="T2")
    ) == "slack:T2"


def test_whatsapp_and_bluebubbles_scope_to_sender():
    assert resolve_gateway_auth_scope(
        SessionSource(platform=Platform.WHATSAPP, chat_id="group", user_id="whatsapp:+1 (555) 010-0000")
    ) == "whatsapp:15550100000"
    assert resolve_gateway_auth_scope(
        SessionSource(platform=Platform.BLUEBUBBLES, chat_id="chat-guid", user_id="+15550100001")
    ) == "bluebubbles:+15550100001"


def test_whatsapp_dm_scope_can_fallback_to_chat_id():
    assert resolve_gateway_auth_scope(
        SessionSource(
            platform=Platform.WHATSAPP,
            chat_id="15550100000@s.whatsapp.net",
            chat_type="dm",
        )
    ) == "whatsapp:15550100000"


def test_whatsapp_group_scope_uses_group_chat_not_sender():
    assert resolve_gateway_auth_scope(
        SessionSource(
            platform=Platform.WHATSAPP,
            chat_id="120363001234567890@g.us",
            chat_type="group",
            user_id="15550100000@s.whatsapp.net",
        )
    ) == "whatsapp:120363001234567890@g.us"


def test_whatsapp_group_without_sender_still_scopes_to_group_chat():
    assert resolve_gateway_auth_scope(
        SessionSource(
            platform=Platform.WHATSAPP,
            chat_id="120363001234567890@g.us",
            chat_type="group",
        )
    ) == "whatsapp:120363001234567890@g.us"


def test_bluebubbles_group_scope_uses_group_chat_not_sender():
    assert resolve_gateway_auth_scope(
        SessionSource(
            platform=Platform.BLUEBUBBLES,
            chat_id="chat-guid;+;participant-a;+;participant-b",
            chat_type="group",
            user_id="+15550100001",
        )
    ) == "bluebubbles:chat-guid;+;participant-a;+;participant-b"


def test_whatsapp_broadcast_pseudo_chats_have_no_auth_scope():
    for chat_id in ("status@broadcast", "1234@broadcast", "120363999999999999@newsletter"):
        assert resolve_gateway_auth_scope(
            SessionSource(
                platform=Platform.WHATSAPP,
                chat_id=chat_id,
                chat_type="dm",
            )
        ) is None


def test_gateway_auth_dir_is_denied_to_file_tools():
    blocked = Path.home() / ".flage" / "gateway-auth" / "abc" / "auth.json"
    assert gateway_auth_path_error(blocked)


def test_hosted_gateway_auth_dir_is_denied_to_file_tools(tmp_path):
    hosted_auth = tmp_path / "hosted" / "state" / "slack_T123" / "auth"
    hosted_auth.mkdir(parents=True)
    tokens = set_session_vars(platform="slack", hosted_gateway_auth_root=str(hosted_auth))
    try:
        assert gateway_auth_path_error(hosted_auth / "growth.json")
    finally:
        clear_session_vars(tokens)


def test_unrelated_temp_path_is_not_denied_as_gateway_auth(tmp_path):
    assert gateway_auth_path_error(tmp_path / "unrelated" / "file.txt") is None


def test_hosted_mode_uses_hosted_state_bootstrap_auth_root_without_scope(monkeypatch, tmp_path):
    monkeypatch.setenv("MOCHI_HOSTED_MODE", "true")
    monkeypatch.delenv("MOCHI_HOSTED_GATEWAY_AUTH_ROOT", raising=False)
    monkeypatch.setenv("MOCHI_HOSTED_STATE_ROOT", str(tmp_path / "hosted"))
    tokens = set_session_vars(platform="slack")
    try:
        assert mcp_tool._gateway_auth_root() == tmp_path / "hosted" / "bootstrap" / "auth"
    finally:
        clear_session_vars(tokens)


def test_hosted_mode_without_any_hosted_root_fails_closed(monkeypatch):
    monkeypatch.setenv("MOCHI_HOSTED_MODE", "true")
    monkeypatch.delenv("MOCHI_HOSTED_GATEWAY_AUTH_ROOT", raising=False)
    monkeypatch.delenv("MOCHI_HOSTED_STATE_ROOT", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    tokens = set_session_vars(platform="slack")
    try:
        try:
            mcp_tool._gateway_auth_root()
        except RuntimeError as exc:
            assert "MOCHI_HOSTED_STATE_ROOT" in str(exc)
        else:
            raise AssertionError("hosted MCP auth root should fail closed without hosted roots")
    finally:
        clear_session_vars(tokens)


def test_gateway_mode_without_any_hosted_root_fails_closed(monkeypatch):
    monkeypatch.delenv("MOCHI_HOSTED_MODE", raising=False)
    monkeypatch.setenv("_HERMES_GATEWAY", "1")
    monkeypatch.delenv("MOCHI_HOSTED_GATEWAY_AUTH_ROOT", raising=False)
    monkeypatch.delenv("MOCHI_HOSTED_STATE_ROOT", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    tokens = set_session_vars(platform="slack")
    try:
        try:
            mcp_tool._gateway_auth_root()
        except RuntimeError as exc:
            assert "MOCHI_HOSTED_STATE_ROOT" in str(exc)
        else:
            raise AssertionError("gateway MCP auth root should fail closed without hosted roots")
    finally:
        clear_session_vars(tokens)


def test_hosted_filesystem_root_jails_file_tools(tmp_path, monkeypatch):
    hosted_root = tmp_path / "hosted" / "state" / "slack_T123" / "conversations" / "slack_T123_C456" / "files"
    hosted_root.mkdir(parents=True)
    inside = hosted_root / "ok.txt"
    inside.write_text("ok\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("no\n", encoding="utf-8")
    monkeypatch.setenv("TERMINAL_CWD", str(hosted_root))
    tokens = set_session_vars(platform="slack", hosted_filesystem_root=str(hosted_root))
    try:
        assert hosted_filesystem_path_error(inside) is None
        assert hosted_filesystem_path_error(outside)
        assert "1|ok" in read_file_tool(str(inside), limit=1)
        assert "escapes hosted filesystem root" in read_file_tool(str(outside), limit=1)
        assert "escapes hosted filesystem root" in write_file_tool(str(outside), "blocked")
    finally:
        clear_session_vars(tokens)


def test_hosted_filesystem_root_jails_terminal_workdir(tmp_path, monkeypatch):
    hosted_root = tmp_path / "hosted" / "files"
    outside = tmp_path / "outside"
    hosted_root.mkdir(parents=True)
    outside.mkdir()
    monkeypatch.setenv("TERMINAL_ENV", "local")
    monkeypatch.setenv("TERMINAL_CWD", str(outside))
    tokens = set_session_vars(platform="slack", hosted_filesystem_root=str(hosted_root))
    try:
        allowed = terminal_tool("pwd")
        blocked = terminal_tool("pwd", workdir=str(outside))
    finally:
        clear_session_vars(tokens)

    assert str(hosted_root) in allowed
    assert "escapes hosted filesystem root" in blocked


def test_hosted_mode_without_filesystem_root_blocks_paths(monkeypatch):
    monkeypatch.setenv("MOCHI_HOSTED_MODE", "true")
    tokens = set_session_vars(platform="slack", hosted_filesystem_root="")
    try:
        error = hosted_filesystem_path_error("/tmp/outside.txt")
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "hosted filesystem root is not set" in error


def test_hosted_mode_disables_local_terminal_backend(tmp_path, monkeypatch):
    hosted_root = tmp_path / "hosted" / "files"
    hosted_root.mkdir(parents=True)
    monkeypatch.setenv("MOCHI_HOSTED_MODE", "true")
    monkeypatch.setenv("TERMINAL_ENV", "local")
    tokens = set_session_vars(platform="slack", hosted_filesystem_root=str(hosted_root))
    try:
        result = terminal_tool("pwd")
    finally:
        clear_session_vars(tokens)

    assert "Local terminal is disabled in hosted mode" in result
