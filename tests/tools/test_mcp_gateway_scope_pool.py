from gateway.session_context import clear_session_vars, set_session_vars
from tools.mcp_tool import (
    MCPAuthScopePool,
    _assert_gateway_growth_mcp_is_explicitly_scoped,
    _bootstrap_gateway_config,
    _should_use_per_auth_scope,
)


def test_scoped_growth_mcp_env_is_deterministic(monkeypatch):
    monkeypatch.delenv("GROWTH_MCP_BROWSER_PROVIDER", raising=False)
    tokens = set_session_vars(
        platform="slack",
        gateway_auth_scope="slack:T123",
        hosted_gateway_auth_root="/tmp/mochi-hosted/state/slack_T123/auth",
        hosted_scope_assertion="assertion-secret",
    )
    pool = MCPAuthScopePool(
        "growth",
        {
            "command": "node",
            "args": ["dist/index.js", "serve"],
            "env": {"EXISTING": "1"},
            "gateway_browser_provider": "chrome",
        },
    )

    try:
        cfg = pool._scoped_config("slack:T123")
        env = cfg["env"]

        assert env["EXISTING"] == "1"
        assert env["GROWTH_MCP_GATEWAY"] == "1"
        assert env["GROWTH_MCP_AUTH_SCOPE"] == "slack:T123"
        assert env["GROWTH_MCP_HOSTED_SCOPE_ASSERTION"] == "assertion-secret"
        assert env["GROWTH_MCP_BROWSER_PROVIDER"] == "chrome"
        assert env["GROWTH_MCP_AUTH_DIR"] == "/tmp/mochi-hosted/state/slack_T123/auth/5249716b4889950720258f96f38360b7"
        assert env["GROWTH_MCP_BROWSER_PROFILE_DIR"] == env["GROWTH_MCP_AUTH_DIR"] + "/browser"
    finally:
        clear_session_vars(tokens)


def test_bootstrap_config_uses_hosted_bootstrap_auth_dir(monkeypatch, tmp_path):
    hosted_state_root = tmp_path / "hosted"
    monkeypatch.setenv("MOCHI_HOSTED_MODE", "true")
    monkeypatch.setenv("MOCHI_HOSTED_STATE_ROOT", str(hosted_state_root))

    cfg = _bootstrap_gateway_config({"command": "node", "args": ["dist/index.js"], "env": {}})
    env = cfg["env"]

    assert env["GROWTH_MCP_GATEWAY"] == "1"
    assert env["GROWTH_MCP_AUTH_SCOPE"].startswith("bootstrap:")
    assert env["GROWTH_MCP_AUTH_DIR"].startswith(str(hosted_state_root / "bootstrap" / "auth"))


def test_per_auth_scope_is_explicit():
    assert _should_use_per_auth_scope(
        "growth",
        {
            "command": "npx",
            "args": ["-y", "growth-mcp@latest"],
            "per_auth_scope": True,
        },
    )
    assert not _should_use_per_auth_scope(
        "growth",
        {
            "command": "npx",
            "args": ["-y", "growth-mcp@latest"],
        },
    )


def test_gateway_growth_mcp_without_explicit_scope_fails_closed(monkeypatch):
    monkeypatch.setenv("_HERMES_GATEWAY", "1")

    try:
        _assert_gateway_growth_mcp_is_explicitly_scoped(
            "growth",
            {"command": "npx", "args": ["-y", "growth-mcp@latest", "serve"]},
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected unscoped Growth MCP gateway config to fail")

    assert "per_auth_scope: true" in message
    assert "Refusing to start an unscoped Growth MCP process" in message


def test_gateway_growth_mcp_with_explicit_false_scope_fails_closed(monkeypatch):
    monkeypatch.setenv("_HERMES_GATEWAY", "1")

    try:
        _assert_gateway_growth_mcp_is_explicitly_scoped(
            "growth",
            {"command": "npx", "args": ["-y", "growth-mcp@latest", "serve"], "per_auth_scope": False},
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected explicitly unscoped Growth MCP gateway config to fail")

    assert "per_auth_scope: true" in message


def test_gateway_non_growth_mcp_without_explicit_scope_is_allowed(monkeypatch):
    monkeypatch.setenv("_HERMES_GATEWAY", "1")

    _assert_gateway_growth_mcp_is_explicitly_scoped(
        "filesystem",
        {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]},
    )
