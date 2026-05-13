from __future__ import annotations


def test_default_soul_identifies_as_mochi_from_verbiflow() -> None:
    from hermes_cli.default_soul import DEFAULT_SOUL_MD

    assert "You are Mochi" in DEFAULT_SOUL_MD
    assert "developed by Verbiflow" in DEFAULT_SOUL_MD
    assert "Hermes Agent" not in DEFAULT_SOUL_MD
    assert "Nous Research" not in DEFAULT_SOUL_MD


def test_prompt_builder_default_identity_identifies_as_mochi() -> None:
    from agent.prompt_builder import DEFAULT_AGENT_IDENTITY, HERMES_AGENT_HELP_GUIDANCE

    assert "You are Mochi" in DEFAULT_AGENT_IDENTITY
    assert "developed by Verbiflow" in DEFAULT_AGENT_IDENTITY
    assert "Hermes Agent" not in DEFAULT_AGENT_IDENTITY
    assert "Nous Research" not in DEFAULT_AGENT_IDENTITY
    assert "using Mochi" in HERMES_AGENT_HELP_GUIDANCE


def test_whatsapp_reply_prefix_uses_mochi() -> None:
    from gateway.platforms.whatsapp import WhatsAppAdapter

    assert "*Mochi*" in WhatsAppAdapter.DEFAULT_REPLY_PREFIX
    assert "Hermes Agent" not in WhatsAppAdapter.DEFAULT_REPLY_PREFIX


def test_banner_version_label_uses_mochi(monkeypatch) -> None:
    import hermes_cli.banner as banner

    monkeypatch.setattr(banner, "get_git_banner_state", lambda: None)

    assert banner.format_banner_version_label().startswith("Mochi v")
