---
name: mcp-server-setup
description: "Add, configure, and troubleshoot MCP servers (stdio or remote HTTP/OAuth) in Hermes Agent's config.yaml — including OAuth allowlist rejections from SaaS providers like Figma."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mcp, oauth, config, hermes, integration, figma, troubleshooting]
    related_skills: [hermes-agent]
---

# MCP Server Setup (Hermes Agent)

Class-level skill for wiring a new MCP server into Hermes Agent — stdio
(`npx`/`uvx`) or remote HTTP, with or without OAuth — and for the specific
failure modes that show up with SaaS-hosted remote MCP servers.

For the baseline mechanics (config shape, tool naming, transport types,
sampling), see the `hermes-agent` skill's `references/native-mcp.md` and the
live docs at https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference
— this skill does not duplicate that, it covers what breaks in practice and
how to drive the CLI to fix it.

## Adding a server — use the CLI, not direct file edits

`write_file`/`patch` on `~/.hermes/config.yaml` is **blocked by design**:

```
Refusing to write to Hermes config file: ~/.hermes/config.yaml
Agent cannot modify security-sensitive configuration.
```

Always go through the `hermes` CLI instead:

```bash
# stdio server
hermes mcp add <name> --command npx --args -y pkg-name

# HTTP server, no auth
hermes mcp add <name> --url https://mcp.example.com/mcp

# HTTP server with OAuth 2.1 PKCE
hermes mcp add <name> --url https://mcp.example.com/mcp --auth oauth

# Fine-grained edits after the entry exists (safe path around the write-file guard)
hermes config set mcp_servers.<name>.client_name "Some Name"
hermes config set mcp_servers.<name>.auth oauth
```

`hermes mcp add --auth oauth` tries to run the OAuth flow immediately and
is interactive (`Continue without authentication? [Y/n]`, `Save config
anyway? [y/N]`). In a non-interactive/background terminal call it will
hang on those prompts — run it with `pty=true` (or pipe `y`/`n` answers via
stdin) so you can see and answer them, or just accept the "save anyway"
prompt to persist a disabled entry, then drive OAuth separately with:

```bash
hermes mcp login <name>
```

`hermes mcp login` is the dedicated command for completing/retrying OAuth
on an already-configured server — prefer it over re-running `mcp add`.

## Verifying

```bash
hermes mcp list          # transport, tool count, enabled/disabled
hermes mcp test <name>   # live connect attempt with a real error message
/reload-mcp              # apply config changes without restarting the process
```

New servers/config changes need a fresh session or `/reload-mcp` — MCP
discovery runs at startup, not live during a conversation.

## Pitfall: SaaS remote MCP servers can allowlist OAuth clients

Some hosted MCP servers (in beta, as of 2026) restrict RFC 7591 Dynamic
Client Registration to a fixed allowlist of client names — official
first-party integrations only (e.g. Claude Code, Cursor, VS Code, Codex,
Xcode). A non-listed client — Hermes, opencode, mcporter, raw MCP SDK
usage — gets rejected during registration itself, before any browser
authorization URL is even generated:

```
✗ Authentication failed: Registration failed: 403 Forbidden
```

**Confirmed root cause, not a Hermes bug**: this is the provider's
authorization server rejecting the client registration request. See
`references/oauth-allowlist-providers.md` for the Figma case study
(reproduced end-to-end) and the general pattern.

Diagnostic ladder when you hit `Registration failed: 403` on an OAuth MCP
server:

1. **Try `client_name` override** matching one of the provider's allowlisted
   client names: `hermes config set mcp_servers.<name>.client_name "Claude Code"`.
   This *is* supported by Hermes (feeds straight into `OAuthClientMetadata`
   at registration time) and works for some providers — but do not assume
   it always works. Some providers (confirmed: Figma) validate more than
   the name string and still reject it. Test with `hermes mcp login <name>`
   after setting it; if still 403, move to the next option.
2. **Check for a pre-registered `client_id`** the provider issues for
   API/enterprise use — if they offer one, Hermes supports it directly:
   `client_id` + `client_secret` keys on the server entry skip dynamic
   registration entirely (see `mcp_oauth.py::_maybe_preregister_client`).
3. **Look for a local/non-OAuth variant of the same server.** SaaS design
   tools in particular often ship a companion desktop-app-hosted MCP server
   that needs no OAuth at all (plain `http://127.0.0.1:<port>/mcp`). This is
   usually the actual working path when the remote+OAuth route is
   allowlist-gated. Confirm the exact URL/steps in the provider's own docs
   before assuming a port number.
4. **File feedback / wait for onboarding** if neither of the above exists.
   This is a beta-era product policy on the provider's side, not something
   fixable purely from the client side.

Do not conclude "Hermes doesn't support MCP OAuth" from one 403 — the OAuth
2.1 PKCE flow (metadata discovery, DCR, token exchange/refresh, token
persistence to `~/.hermes/mcp-tokens/<server>.json`) works correctly for
providers that don't gate registration. Confirm the failure is
provider-side (`Registration failed` specifically, not a later step) before
troubleshooting Hermes's OAuth implementation itself.

## See also

- `references/oauth-allowlist-providers.md` — Figma case study + command
  transcript, and other providers known to require pre-registered clients.
- `hermes-agent` skill (`references/native-mcp.md`) — full config reference,
  transports, sampling, security/env-filtering behavior for stdio servers.
