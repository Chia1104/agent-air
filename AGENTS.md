# Agent Air project rules

- This repository is the source of truth for synchronizing the user's AI agent settings across computers. Changes should remain portable, deterministic, and safe to restore on a new machine.
- Keep real credentials, OAuth tokens, cookies, private keys, and machine-only overrides out of Git.
- Public MCP configs must reference environment variables such as `${MCP_TOKEN}` rather than embedding values.
- `private/` is intentionally gitignored but is not a security boundary: agents may read it when explicitly needed and policy permits.
- After changing snapshots, run `python3 scripts/check-secrets.py` and `git diff --check`.
- Do not vendor runtime state, sessions, caches, auth databases, `.hub`, Hermes curator backups, or Codex built-in `.system` skills.
- Treat `skills/shared` as the canonical cross-agent skill set. If a declared skill `name` exists in shared, do not keep any agent-specific copy or variant; installation must use the shared version. Keep only unique per-agent skills under `skills/<agent>`.
- When an identical skill tree is present for two or more agents, promote one copy to `skills/shared` and remove all per-agent copies. Never deduplicate divergent same-name variants unless shared already defines the canonical version.
- Track third-party plugins as declarative manifests, not downloaded caches or marketplace checkouts. Track local Hermes/OpenCode plugin source code, but exclude credentials, runtime state, and dependency directories.
