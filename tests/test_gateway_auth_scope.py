from pathlib import Path

from gateway.config import Platform
from gateway.session import SessionSource, resolve_gateway_auth_scope
from tools.path_security import gateway_auth_path_error


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
