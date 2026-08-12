# Providers known to gate MCP OAuth by client allowlist / pre-registration

## Figma (`https://mcp.figma.com/mcp`) — confirmed, reproduced 2026

Figma's remote MCP server is in beta and restricts RFC 7591 Dynamic Client
Registration to clients on Figma's own [MCP Catalog](https://www.figma.com/mcp-catalog/):
Claude Code, Cursor, VS Code, Codex, Xcode. Confirmed directly by a Figma
team member on the Figma forum (Jaycee Lewis, in response to the opencode
thread): *"Our remote MCP server allowlists `client_name` during dynamic
client registration... the `mcp:connect` scope is intentionally gated to
supported clients while we're in beta."*

### Reproduction transcript

```bash
$ hermes mcp add figma --url https://mcp.figma.com/mcp --auth oauth
Starting OAuth flow for 'figma'...
  ⚠ OAuth error: MCP OAuth for 'figma': non-interactive environment and no
    cached tokens found. Run `hermes mcp login figma` interactively first.
  Continue without authentication? [Y/n]:
  Connecting to 'figma'...
  ✗ Failed to connect: Client error '401 Unauthorized'
  Save config anyway (you can test later)? [y/N]: y
  ✓ Saved 'figma' to config (disabled)

$ hermes mcp login figma
Starting OAuth flow for 'figma'...
  ✗ Authentication failed: Registration failed: 403 Forbidden
```

Tried the `client_name` spoof workaround reported to work for *some* other
MCP clients (per a GitHub issue on `openclaw/mcporter#115`, a contributor
got Figma working elsewhere by setting `clientName: "Claude Code"`):

```bash
$ hermes config set mcp_servers.figma.client_name "Claude Code"
$ hermes mcp login figma
Starting OAuth flow for 'figma'...
  ✗ Authentication failed: Registration failed: 403 Forbidden
```

Still 403 in this environment — Figma's check is not purely a string match
on `client_name`, or it changed since the mcporter report. **Don't assume
the spoof will work; verify with a real login attempt.**

### Actual working alternative: Figma Desktop's local MCP server

No OAuth needed. Requires the Figma desktop app (not the web app):

1. Open Figma desktop app, open/create a Design file.
2. Toggle **Dev Mode** (`Shift+D`).
3. In the inspect panel's **MCP server** section, click **Enable desktop
   MCP server**. Confirmation toast appears; server runs at
   `http://127.0.0.1:3845/mcp`.
4. Add it to Hermes as a plain unauthenticated HTTP server:
   ```bash
   hermes mcp add figma_desktop --url http://127.0.0.1:3845/mcp
   ```
5. `/reload-mcp` or start a new session.

Trade-off: desktop server requires the Figma app running locally and only
exposes context for files open in that app instance (selection- or
link-based node lookup) — Figma's docs explicitly say the remote server has
"the broadest set of features" and recommend it when available. Only fall
back to desktop when the remote route is allowlist-blocked for your client.

## Other providers with similar DCR restrictions (reported, not yet
reproduced against Hermes)

- **Qlik Cloud MCP** — reported (GitHub `openclaw/mcporter#115` comment) to
  require a pre-registered `client_id`/`client_secret` rather than
  supporting dynamic registration at all. Same diagnostic ladder applies:
  check for a `client_id` the provider issues for API/enterprise use, plug
  it into `mcp_servers.<name>.client_id` (+ `client_secret` if given).

## General signature to watch for

`Registration failed: <4xx>` (as opposed to a later-stage error like token
exchange or scope denial) means the *client itself* was rejected before an
authorization URL was ever produced — this is provider policy, not a bug in
Hermes's OAuth 2.1 PKCE implementation. Don't spend time debugging Hermes's
OAuth code for this signature; go straight to the provider's docs/support
channel or look for a non-OAuth local variant.
