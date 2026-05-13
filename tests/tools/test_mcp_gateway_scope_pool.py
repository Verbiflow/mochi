from tools.mcp_tool import (
    MCPAuthScopePool,
    _bootstrap_gateway_config,
    _should_use_per_auth_scope,
)


def test_scoped_growth_mcp_env_is_deterministic(monkeypatch):
    monkeypatch.delenv("GROWTH_MCP_BROWSER_PROVIDER", raising=False)
    pool = MCPAuthScopePool(
        "growth",
        {
            "command": "node",
            "args": ["dist/index.js", "serve"],
            "env": {"EXISTING": "1"},
            "gateway_browser_provider": "chrome",
        },
    )

    cfg = pool._scoped_config("slack:T123")
    env = cfg["env"]

    assert env["EXISTING"] == "1"
    assert env["GROWTH_MCP_GATEWAY"] == "1"
    assert env["GROWTH_MCP_AUTH_SCOPE"] == "slack:T123"
    assert env["GROWTH_MCP_BROWSER_PROVIDER"] == "chrome"
    assert env["GROWTH_MCP_AUTH_DIR"].endswith("/.flage/gateway-auth/5249716b4889950720258f96f38360b7")
    assert env["GROWTH_MCP_BROWSER_PROFILE_DIR"].endswith("/browser")


def test_bootstrap_config_does_not_use_host_auth_dir():
    cfg = _bootstrap_gateway_config({"command": "node", "args": ["dist/index.js"], "env": {}})
    env = cfg["env"]

    assert env["GROWTH_MCP_GATEWAY"] == "1"
    assert env["GROWTH_MCP_AUTH_SCOPE"].startswith("bootstrap:")
    assert "/.flage/gateway-auth/" in env["GROWTH_MCP_AUTH_DIR"]


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
