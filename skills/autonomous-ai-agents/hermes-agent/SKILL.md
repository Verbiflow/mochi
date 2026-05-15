---
name: hermes-agent
description: "Configure, extend, or contribute to Mochi, the Verbiflow-maintained Hermes-compatible agent."
version: 3.0.0
author: Verbiflow
license: MIT
platforms: [linux, macos, windows]
metadata:
  mochi:
    tags: [mochi, hermes-compatible, setup, configuration, multi-agent, gateway, mcp, development]
    homepage: https://github.com/Verbiflow/mochi
    related_skills: [claude-code, codex]
  compatibility:
    command_name: hermes
    data_dir: ~/.hermes
    install_dir: ~/.hermes/hermes-agent
---

# Mochi

Mochi is the Verbiflow-maintained fork of Hermes Agent. Treat Mochi as the
project and product name in user-facing copy. The CLI command, Python package
namespace, service names, data directory, and default git install path still
use Hermes names for compatibility:

- Command: `hermes`
- Data directory: `~/.hermes`
- Source checkout on installed hosts: `~/.hermes/hermes-agent`
- Python modules: `hermes_cli`, `hermes_state`, and related internal names

Do not "clean up" those compatibility names unless the migration plan explicitly
covers command aliases, services, data migration, docs, and tests. In prose,
runtime messages, Slack/WhatsApp/iMessage replies, setup prompts, and manifests,
prefer Mochi.

Mochi runs in terminals, messaging gateways, IDE/MCP surfaces, and background
schedulers. It supports provider-agnostic model routing, tools, skills,
persistent memory, profiles, MCP servers, cron jobs, webhooks, plugins, and
multi-platform gateway adapters.

Source of truth:

- Repo: `https://github.com/Verbiflow/mochi`
- Local docs: `website/docs/`
- Command registry: `hermes_cli/commands.py`
- Runtime config defaults: `hermes_cli/config.py`

## Quick Start

```bash
# New install
curl -fsSL https://raw.githubusercontent.com/Verbiflow/mochi/main/scripts/install.sh | bash

# Migrate an existing Hermes install on a Mac mini without deleting ~/.hermes
curl -fsSL https://raw.githubusercontent.com/Verbiflow/mochi/main/scripts/migrate_to_mochi.sh | bash

# Interactive chat
hermes

# Single query
hermes chat -q "What is the capital of France?"

# Setup wizard
hermes setup

# Change model/provider
hermes model

# Health check
hermes doctor
```

After migration, updates still use the compatibility command:

```bash
hermes update
```

`hermes update` should update from the configured Mochi `origin/main`. If
`origin` still points at `NousResearch/hermes-agent`, gateway-mode updates fail
fast and tell the operator to run the migration script. Interactive CLI update
may offer an explicit `hermes update --migrate-to-mochi` path. It must not
silently switch remotes in unattended gateway mode.

## CLI Reference

No subcommand defaults to interactive chat.

```bash
hermes [flags] [command]

  --version, -V             Show version
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode for parallel agents
  --skills, -s SKILL        Preload skills, comma-separated or repeated
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --pass-session-id         Include session ID in system prompt
```

Common commands:

```bash
hermes chat [flags]
hermes setup [model|terminal|gateway|tools|agent]
hermes model
hermes config
hermes config edit
hermes config set KEY VAL
hermes config migrate
hermes login [--provider P]
hermes logout
hermes doctor [--fix]
hermes status [--all]

hermes tools
hermes tools list
hermes tools enable NAME
hermes tools disable NAME

hermes skills list
hermes skills search QUERY
hermes skills install ID
hermes skills inspect ID
hermes skills config
hermes skills update

hermes mcp serve
hermes mcp add NAME --url URL
hermes mcp add NAME --command COMMAND
hermes mcp list
hermes mcp test NAME
hermes mcp configure NAME

hermes gateway run
hermes gateway install
hermes gateway start
hermes gateway stop
hermes gateway restart
hermes gateway status
hermes gateway setup

hermes slack manifest [--write [PATH]]
hermes whatsapp

hermes sessions list
hermes sessions browse
hermes sessions export OUT

hermes cron list
hermes cron create SCHED
hermes cron edit ID
hermes cron pause ID
hermes cron resume ID
hermes cron run ID
hermes cron remove ID

hermes profile list
hermes profile create NAME
hermes profile use NAME
hermes profile export NAME
hermes profile import FILE

hermes update
hermes pairing list
hermes pairing approve
hermes plugins list
hermes memory setup
hermes memory status
hermes completion bash|zsh
hermes acp
hermes uninstall
```

## Slash Commands

In interactive chat, run `/help` for the authoritative current list. The
registry of record is `hermes_cli/commands.py`; autocomplete, Slack mapping,
Telegram menus, gateway `/commands`, and in-session help all derive from it.

Common commands:

```text
/new or /reset       Fresh session
/clear               Clear screen and start a new CLI session
/retry               Resend last message
/undo                Remove last exchange
/title [name]        Name the session
/compress            Compress context
/stop                Kill background processes
/rollback [N]        Restore filesystem checkpoint
/background <prompt> Run prompt in background
/queue <prompt>      Queue for next turn
/steer <prompt>      Inject a message after next tool call
/agents              Show active agents and tasks
/resume [name]       Resume a named session
/goal [text|sub]     Set or manage a standing goal

/config              Show config in CLI
/model [name]        Show or change model
/personality [name]  Set personality
/reasoning [level]   Set reasoning effort
/verbose             Cycle verbosity
/voice [on|off|tts]  Voice mode
/yolo                Toggle approval bypass
/busy [sub]          Control Enter behavior while Mochi is working
/footer [on|off]     Toggle gateway runtime metadata footer

/tools               Manage tools
/toolsets            List toolsets
/skills              Search/install skills
/skill <name>        Load a skill
/reload-skills       Re-scan installed skills
/reload              Reload env variables
/reload-mcp          Reload MCP servers
/cron                Manage cron jobs
/curator [sub]       Background skill maintenance
/kanban [sub]        Multi-profile work queue
/plugins             List plugins

/approve             Approve a pending gateway command
/deny                Deny a pending gateway command
/restart             Restart gateway
/sethome             Set current chat as the platform home target
/update              Update Mochi
/topic [sub]         Telegram DM topic sessions
/platforms           Platform connection status

/help                Show commands
/commands [page]     Browse gateway commands
/usage               Token usage
/status              Session info
/profile             Active profile info
/debug               Upload debug report
/quit                Exit CLI
```

Gateway behavior note: Mochi no longer sends first-message "No home channel is
set" onboarding spam in normal Slack, WhatsApp, or iMessage conversations.
`/sethome` still exists, and delivery-time failures still tell the operator to
set a home target when a cron job, handoff, or cross-platform delivery actually
needs one.

Home targets are still stored through the platform-specific env/config pattern
used by the gateway, usually `{PLATFORM}_HOME_CHANNEL` plus
`{PLATFORM}_HOME_CHANNEL_NAME`. Some adapters support public/private delivery
for operational notices; do not reintroduce first-contact onboarding as a
shortcut for that.

## Key Paths

```text
~/.hermes/config.yaml       Main configuration
~/.hermes/.env              API keys and secrets
~/.hermes/skills/           Installed skills
~/.hermes/sessions/         Session transcripts
~/.hermes/logs/             Gateway and error logs
~/.hermes/auth.json         OAuth tokens and credential pools
~/.hermes/hermes-agent/     Source checkout on git-installed hosts
~/.flage/gateway-auth/      Gateway-scoped Growth MCP auth and browser state
```

Profiles use `~/.hermes/profiles/<name>/` with the same layout. Development
inside the repo uses a repo-local `.venv`; installed Mac mini runtimes keep the
existing install `venv` under `~/.hermes/hermes-agent/venv`.

Never expose `~/.flage/gateway-auth/**` to the agent through file or terminal
tools. That directory contains scoped auth material for remote gateway users.

## Gateway Platforms

Supported gateway adapters include Telegram, Discord, Slack, WhatsApp, Signal,
Email, SMS, Matrix, Mattermost, Home Assistant, DingTalk, Feishu, WeCom,
BlueBubbles for iMessage, Weixin, API Server, Webhooks, and Open WebUI through
the API Server adapter.

### Slack

Slack user-facing slash entrypoint is `/mochi`, not `/hermes`.

```bash
hermes slack manifest --write
```

The generated manifest should include `/mochi` plus the supported first-class
gateway slash commands. After pulling a version that changes Slack commands,
regenerate the manifest, paste it into Slack app config, save it, and reinstall
the app if Slack prompts for permission updates.

Slack gateway auth scope is workspace-level:

```text
slack:<team_id>
```

Different threads and channels in the same Slack workspace share the same
Growth auth and browser profile. Different Slack workspaces are isolated.
`thread_ts` and Slack `user_id` are intentionally not part of the Growth auth
scope.

### WhatsApp

WhatsApp gateway auth scopes:

```text
whatsapp:<group chat_id>                  # group chats
whatsapp:<canonical sender/private chat>  # direct chats
```

For groups, the group conversation is the auth identifier. Do not split Growth
auth by individual sender inside a group unless the product decision changes.

### BlueBubbles / iMessage

User-facing label is iMessage. Internal adapter name remains BlueBubbles.

iMessage gateway auth scopes:

```text
bluebubbles:<group chat_id>               # group chats
bluebubbles:<sender/private chat>         # direct chats
```

The BlueBubbles webhook registration must preserve literal loopback hosts to
avoid macOS Node resolving `localhost` to IPv6 while the gateway only listens
on IPv4. Current behavior:

- `127.0.0.1` and `0.0.0.0` advertise as `127.0.0.1`
- `localhost` advertises as `127.0.0.1`
- `::1` and `::` advertise as `[::1]`
- LAN/public hosts such as `192.168.1.50` are preserved

Outbound/self messages are ignored through the BlueBubbles `isFromMe` /
`fromMe` / `is_from_me` fields so Mochi does not reply to its own iMessages.

## Gateway MCP And Growth Auth

Growth-like MCP servers in gateway mode must be explicitly scoped:

```yaml
mcp_servers:
  growth:
    command: bun
    args: ["x", "verbiflow-mcp"]
    connect_timeout: 30
    timeout: 120
    per_auth_scope: true
    gateway_browser_provider: chrome   # or safari when profile-aware support is available
```

Mochi intentionally does not infer `per_auth_scope` from server names anymore.
If a Growth-like MCP server is configured during gateway execution without
`per_auth_scope: true`, Mochi fails fast with a setup error instead of sharing
the Mac mini operator's auth state.

`hermes config migrate` can add `per_auth_scope: true` and
`gateway_browser_provider` for known Growth MCP entries in `config.yaml`, while
preserving an explicit `per_auth_scope: false`. Runtime routing still requires
the explicit config field.

For each `gateway_auth_scope`, Mochi spawns or reuses a scoped MCP process with:

```text
GROWTH_MCP_GATEWAY=1
GROWTH_MCP_AUTH_SCOPE=<scope>
GROWTH_MCP_AUTH_DIR=~/.flage/gateway-auth/<scope_hash>
GROWTH_MCP_BROWSER_PROFILE_DIR=~/.flage/gateway-auth/<scope_hash>/browser
GROWTH_MCP_BROWSER_PROVIDER=chrome|safari
```

Growth MCP stores auth, workspace slug, cookie cache, local browser metadata,
and action state under `GROWTH_MCP_AUTH_DIR`.

Browser-backed tools must use the scoped browser identity:

- Chrome uses a scoped `--user-data-dir` under `GROWTH_MCP_BROWSER_PROFILE_DIR`.
- Gateway mode must not scan or read the Mac mini operator's default Chrome
  profiles.
- Safari is allowed only through profile-aware Safari behavior. Do not use the
  old global Safari cookie reader for gateway auth.
- If login is required, tools should open the scoped browser profile and return
  a prompt asking the Slack workspace, WhatsApp chat, or iMessage chat to log in
  there.

Backend/API Growth tools use the scoped auth directory even when no browser is
needed. Browser-backed tools that cannot be constrained to the scoped profile
must stay disabled in gateway mode until fixed.

## Config

Edit config with:

```bash
hermes config edit
hermes config set section.key value
hermes config migrate
```

Important sections:

| Section | Purpose |
| --- | --- |
| `model` | Default model, provider, base URL, API key, context length |
| `agent` | Max turns and tool-use behavior |
| `terminal` | Local/docker/ssh/modal backend, cwd, timeout |
| `compression` | Context compression thresholds |
| `display` | Skin, tool progress, reasoning, cost |
| `stt` / `tts` | Voice transcription and speech output |
| `memory` | Memory provider and user profile toggles |
| `security` | Tirith, redaction, website blocklist |
| `delegation` | Subagent model/provider and concurrency |
| `checkpoints` | Filesystem checkpoint settings |
| `mcp_servers` | MCP process and URL configs |

Local references:

- `website/docs/user-guide/configuration.md`
- `website/docs/reference/environment-variables.md`
- `website/docs/reference/mcp-config-reference.md`

## Providers

Use `hermes model` or `hermes setup` to configure providers. Common env vars:

| Provider | Auth | Key env var |
| --- | --- | --- |
| OpenRouter | API key | `OPENROUTER_API_KEY` |
| Anthropic | API key | `ANTHROPIC_API_KEY` |
| Nous Portal | OAuth | `hermes auth` |
| OpenAI Codex | OAuth | `hermes auth` |
| GitHub Copilot | Token/OAuth | `COPILOT_GITHUB_TOKEN` or Copilot device flow |
| Google Gemini | API key | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| DeepSeek | API key | `DEEPSEEK_API_KEY` |
| xAI / Grok | API key | `XAI_API_KEY` |
| Hugging Face | Token | `HF_TOKEN` |
| Custom OpenAI-compatible endpoint | Config | `model.base_url` and `model.api_key` |

Local reference: `website/docs/integrations/providers.md`.

## Toolsets

Enable or disable tools with:

```bash
hermes tools
hermes tools list
hermes tools enable NAME
hermes tools disable NAME
```

Core toolsets include `web`, `search`, `browser`, `terminal`, `file`,
`code_execution`, `vision`, `image_gen`, `video`, `tts`, `skills`, `memory`,
`session_search`, `delegation`, `cronjob`, `clarify`, `messaging`, `todo`,
`kanban`, `debugging`, `safe`, `spotify`, `homeassistant`, `discord`,
`discord_admin`, `feishu_doc`, `feishu_drive`, `yuanbao`, `rl`, and `moa`.

Tool changes take effect on `/reset` or a new process. Do not mutate tools,
system prompt content, or context shape mid-conversation unless a feature is
explicitly designed to preserve prompt-cache correctness.

## Security And Privacy

Secret redaction is off by default:

```bash
hermes config set security.redact_secrets true
hermes config set security.redact_secrets false
```

Restart after changing it. The setting is snapshotted at startup so the model
cannot flip redaction on or off for its own running process.

Gateway PII redaction:

```bash
hermes config set privacy.redact_pii true
hermes config set privacy.redact_pii false
```

Command approval modes:

```bash
hermes config set approvals.mode manual
hermes config set approvals.mode smart
hermes config set approvals.mode off
```

`--yolo` and `approvals.mode: off` bypass command approvals, but they do not
disable secret redaction.

## Spawning Additional Mochi Processes

Use `delegate_task` for short parallel subtasks inside one agent process. Spawn
separate `hermes` processes when work needs full process isolation, different
profiles, long runtime, PTY interactivity, or independent tool access.

One-shot:

```text
terminal(command="hermes chat -q 'Research GRPO papers and write summary to ~/research/grpo.md'", timeout=300)
terminal(command="hermes chat -q 'Set up CI/CD for ~/myapp'", background=true)
```

Interactive via tmux:

```text
terminal(command="tmux new-session -d -s agent1 -x 120 -y 40 'hermes'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t agent1 'Build a FastAPI auth service' Enter", timeout=15)
terminal(command="sleep 20 && tmux capture-pane -t agent1 -p", timeout=5)
terminal(command="tmux send-keys -t agent1 '/exit' Enter && sleep 2 && tmux kill-session -t agent1", timeout=10)
```

Use `-w` for worktree mode when multiple spawned agents edit the same repo.

## Durable Systems

### Delegation

`delegate_task` spawns subagents inside the parent process. It is useful for
bounded parallel work, but it is not durable. If the parent is interrupted, the
child is cancelled.

### Cron

Cron jobs live under `cron/` and are controlled by the `cronjob` tool,
`hermes cron`, or `/cron`. Jobs support duration schedules, "every" phrases,
five-field cron, ISO timestamps, per-job model/provider overrides, scripts,
working directories, skills, and multi-platform delivery.

Cron delivery to gateway platforms uses home targets. Mochi should explain
missing home targets when delivery needs one, not on every first inbound chat.

### Curator

Curator maintains agent-created skills. It tracks usage, marks idle skills
stale, archives stale skills, and keeps backups. It only touches skills with
agent-created provenance.

### Kanban

Kanban is a durable SQLite work queue for multi-profile or multi-worker
collaboration. Gateway can run the dispatcher, and worker processes receive a
focused `kanban_*` toolset gated by task env vars.

## Install, Migration, And Updates

New installs default to:

```text
https://github.com/Verbiflow/mochi.git
```

Existing Mac mini installs should migrate with:

```bash
curl -fsSL https://raw.githubusercontent.com/Verbiflow/mochi/main/scripts/migrate_to_mochi.sh | bash
```

To override the fork URL while piping the script, put the environment variable
on the `bash` side of the pipe:

```bash
curl -fsSL https://raw.githubusercontent.com/Verbiflow/mochi/main/scripts/migrate_to_mochi.sh \
  | MOCHI_REPO_URL=https://github.com/Verbiflow/mochi.git bash
```

The migration script:

- Keeps `~/.hermes` durable state.
- Detects the existing install checkout.
- Backs up remotes, branch/commit, config, env, durable state, gateway config,
  profile/session/memory metadata, and related state.
- Stops the gateway through `hermes gateway stop` before changing code.
- Sets `origin` to Mochi.
- Removes legacy `upstream` if it points at `NousResearch/hermes-agent`.
- Stashes local changes before fast-forwarding.
- Reinstalls dependencies into the existing runtime `venv`.
- Restarts the gateway only if it was running before migration.

Future `hermes update` should pull Mochi from `origin/main`. If this fork still
wants to import upstream Hermes changes, use the dedicated sync flow that fetches
from a legacy Hermes remote and merges/rebases intentionally. Do not make normal
update paths pull from NousResearch.

## Troubleshooting

### Changes not taking effect

- Tools or skills: run `/reset` or start a new process.
- Gateway config: run `/restart` or `hermes gateway restart`.
- Code changes: restart the CLI or gateway process.
- Slack slash command changes: regenerate and reinstall the Slack manifest.

### Tool not available

1. Check `hermes tools list`.
2. Confirm required env vars exist in `~/.hermes/.env`.
3. Run `/reset` or restart the process.

### Gateway logs

```bash
grep -i "failed to send\\|error" ~/.hermes/logs/gateway.log | tail -20
```

Common gateway problems:

- Discord bot silent: enable Message Content Intent in Discord Bot settings.
- Slack only works in DMs: subscribe to `message.channels` events for public
  channels.
- BlueBubbles local webhook refused: check the registered URL uses a literal
  loopback address matching the gateway bind behavior, not `localhost`.
- Gateway dies on SSH logout: enable linger with
  `sudo loginctl enable-linger "$USER"` on systemd hosts.

### Model/provider issues

1. Run `hermes doctor`.
2. Re-authenticate OAuth providers with `hermes login`.
3. Check API keys in `~/.hermes/.env`.
4. For Copilot, GitHub CLI auth is not enough; use the Copilot-specific device
   flow through `hermes model`.

## Contributor Reference

### Project Layout

```text
mochi/
├── run_agent.py          # Core conversation loop
├── model_tools.py        # Tool discovery and dispatch
├── toolsets.py           # Toolset definitions
├── cli.py                # Interactive CLI
├── hermes_state.py       # SQLite session store
├── agent/                # Prompt, compression, memory, routing, skills
├── hermes_cli/           # CLI subcommands, config, setup, commands
├── tools/                # Tool implementations and registry
├── gateway/              # Messaging gateway and platform adapters
├── cron/                 # Scheduler
├── tests/                # Pytest suite
└── website/              # Docusaurus docs
```

### Adding A Tool

1. Add a `tools/<name>.py` module with `registry.register(...)`.
2. Return JSON strings from handlers.
3. Add a `check_fn` and `requires_env` when requirements are conditional.
4. Add the tool to the appropriate toolset in `toolsets.py`.
5. Add focused tests for the real handler path.

Use `get_hermes_home()` for paths. Do not hardcode `~/.hermes` in code paths
that must be profile-aware.

### Adding A Slash Command

1. Add `CommandDef` in `hermes_cli/commands.py`.
2. Add CLI handling in `cli.py`.
3. Add gateway handling in `gateway/run.py` when the command should work from
   messaging platforms.
4. Add tests for command resolution and any platform-specific routing.

For Slack, ensure the generated manifest remains correct. `/mochi` is the
parent command.

### Testing

Use the repo-local uv environment for Mochi development:

```bash
cd mochi
uv sync --extra all --extra messaging --extra slack
uv run ruff check gateway/session.py tests/test_gateway_auth_scope.py
HERMES_TEST_WORKERS=4 scripts/run_tests.sh tests/test_gateway_auth_scope.py
```

Run focused tests for changed areas first. The full suite is large and some
tests require optional dependencies or host services; do not claim a clean full
suite unless it was actually run and passed in the current environment.

Tests redirect `HERMES_HOME` to temporary directories when written correctly.
New tests must not touch a developer's real `~/.hermes` or the Mac mini gateway
auth directory.

Windows notes:

- `scripts/run_tests.sh` expects POSIX venv layouts.
- Use direct `python -m pytest ... -n 0` on Windows when needed.
- Add skip guards for POSIX-only syscalls, POSIX mode bits, and Unix signals.
- If tests monkeypatch `sys.platform`, also patch `platform.system()` and
  related platform helpers when the code under test reads both.

### Environment Prompt Hints

Host/backend facts are emitted from
`agent/prompt_builder.py::build_environment_hints()`.

- Local terminal backend may describe host OS, home, cwd, shell, and Windows
  notes.
- Remote terminal backends must suppress host filesystem facts and describe the
  backend environment instead.
- When `TERMINAL_ENV != "local"`, file tools run inside the backend container,
  not on the host.

### Commit Conventions

```text
type: concise subject line

Optional body.
```

Common types: `fix:`, `feat:`, `refactor:`, `docs:`, `chore:`.

### Rules That Matter

- Preserve prompt-cache correctness; do not change tools, context shape, or
  system prompt mid-session without an explicit cache-safe design.
- Preserve message role alternation.
- Use `get_hermes_home()` for profile-aware paths.
- Put config in `config.yaml` and secrets in `.env`.
- Keep runtime user-facing brand as Mochi while preserving compatibility
  command/package names until there is a full migration plan.
- Gateway Growth MCP auth must be scoped per `gateway_auth_scope`.
- Never let gateway browser-backed tools read the Mac mini operator's default
  Chrome or Safari session state.
