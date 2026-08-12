---
name: agent-config-portability
description: "Use when versioning multi-agent skills, MCP, and configs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [agents, skills, mcp, config, migration, secrets, dotfiles, deduplication]
---

# Agent Configuration Portability

## When to Use

Use this skill when consolidating, versioning, restoring, or migrating configuration for multiple AI agents (Hermes, Claude Code, Codex, Cursor, OpenCode, Gemini, or similar), especially when the work involves shared skills, MCP definitions, secret-safe configs, or installation on another machine.

The goal is a small, auditable repository that preserves portable behavior without committing credentials, runtime state, caches, or duplicate skills.

## Core model

Separate the repository into four layers:

1. **Canonical shared skills** — one directory such as `skills/shared/`.
2. **Agent-only skills** — only skills whose declared frontmatter `name` does not exist in shared.
3. **Sanitized configs** — MCP and agent settings with secret values replaced by environment references.
4. **Ignored private data** — local environment files or overrides that Git never tracks.

Do not treat tool installation caches, OAuth stores, sessions, history, databases, generated indexes, backups, or bundled internal skills as portable configuration.

## Shared skills are authoritative

Deduplicate by the skill's declared frontmatter `name`, not merely by directory name, path, or content hash.

- If `skills/shared` contains a skill name, remove every agent-specific copy with that name.
- This applies even when the agent-specific copy is a modified variant.
- Do not silently prefer an agent-specific variant during installation.
- Install the shared skill once, then expose it to each agent with a relative symlink when supported.
- Keep an agent-specific skill only when its declared name is absent from shared.
- Fail closed at install time if the repository still contains a duplicate name; tell the operator to rerun the snapshot/dedup step.

This prevents drift where nearly identical skills evolve independently and makes the repository's source of truth obvious.

See `references/shared-skills-dedup.md` for an implementation and verification checklist.

## Snapshot workflow

1. Inventory each agent's config and skills without printing credential values.
2. Copy the canonical shared skill tree.
3. Copy non-symlink agent skill trees while excluding provider-managed or runtime directories.
4. Parse every `SKILL.md` frontmatter name in shared.
5. Recursively remove agent-specific skill roots whose declared name is in the shared set.
6. Remove empty category directories left by deduplication.
7. Sanitize configs before writing them to the repository.
8. Produce a manifest with both:
   - repository state after deduplication; and
   - source state showing original local and symlinked skills.
9. Run syntax, secret, duplicate-name, and install tests.

Snapshot scripts should be deterministic and safe to rerun. Report post-dedup file counts and sizes, not the pre-dedup copy totals.

## Secret-safe MCP and config handling

Public configs should contain references such as `${TOKEN}` or `${env:TOKEN}`, never real credentials.

Examples:

```yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

```yaml
mcp_servers:
  internal:
    url: https://mcp.example.com/mcp
    headers:
      Authorization: "Bearer ${INTERNAL_MCP_TOKEN}"
```

For OAuth MCP servers, preserve the server URL and `auth: oauth`, but do not copy token-store files. Reauthenticate on the destination machine.

A `.gitignore` entry is not an access-control boundary. Agents and shell tools can still read ignored files if filesystem policy allows. Use ignored files for preventing accidental commits; use an OS keychain, password manager, OAuth, or runtime injection when an agent must not receive the secret itself.

## Installer behavior

Default to dry-run. Require an explicit flag for writes.

A safe installer should:

1. Back up paths it replaces.
2. Install the canonical shared tree once.
3. Install only unique agent-specific skills.
4. Link every shared skill into each supported agent.
5. Validate that the repo has no shared/agent duplicate names before writing anything.
6. Optionally install sanitized configs separately from skills.
7. Never copy auth databases, OAuth tokens, sessions, caches, or histories.

When a category-based agent tree contains nested skills, do not deduplicate only top-level directories. Discover `SKILL.md` recursively and remove the exact skill root.

## Required verification

Before declaring the repository ready:

- Parse all JSON, YAML, and TOML configs.
- Compile or lint snapshot, installer, and scan scripts.
- Confirm zero duplicate declared skill names between shared and agent-specific trees.
- Run the installer against a temporary HOME or equivalent isolated target.
- Assert representative shared skills become symlinks for multiple agents.
- Assert representative unique agent skills remain real directories.
- Run a secret scanner over tracked and untracked non-ignored candidate files.
- Negative-test the scanner with a temporary realistic-looking fake credential and verify it rejects the file.
- Run whitespace/diff checks.
- Verify private paths are actually ignored with `git check-ignore`.

## Secret scanner guidance

Scan credential prefixes, private-key headers, bearer tokens, JWT shapes, and sensitive assignments in config files. Avoid noisy generic-assignment rules over source code and documentation, where `token = variable` and public deterministic IDs are common. Still scan every file for high-confidence credential formats and private keys.

Never print matched secret values in scanner output. Report only file, line, and finding class.

## Pitfalls

- **Content-hash-only deduplication:** misses modified variants that the shared-source policy says to discard.
- **Directory-name-only deduplication:** misses nested/category skills and frontmatter names that differ from folder names.
- **Copying then overlaying:** may leave stale files from an older skill version. Replace a skill root atomically or back it up first.
- **Ignoring secrets as security:** `.gitignore` prevents tracking, not reading.
- **Copying OAuth stores:** makes migrations fragile and risks credential exposure; reauthenticate instead.
- **Reporting source inventory as repo state:** manifests should distinguish pre-dedup source layout from post-dedup repository layout.
- **Testing only dry-run output:** always perform one real install into an isolated temporary home.
