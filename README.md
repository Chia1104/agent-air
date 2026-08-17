# Agent Air

Agent Air is the source of truth for syncing personal AI agent settings across computers. Clone this repository on a new machine to restore a consistent, reviewable agent environment without committing secrets.

It includes:

- Shared and agent-specific skills
- Non-secret settings for Hermes, Claude Code, Codex, Cursor, OpenCode, and Gemini
- MCP server definitions with tokens replaced by environment variable references
- Snapshot, installation, test, and secret-scanning scripts

## Repository layout

```text
configs/                 Sanitized agent settings
  hermes/
  claude/
  codex/
  cursor/
  opencode/
  gemini/
skills/
  shared/                Canonical shared skills from ~/.agents/skills
  hermes/                Hermes-specific skills
  claude|codex|.../      Unique agent-specific skills
manifests/inventory.json Snapshot inventory
scripts/snapshot.py      Capture settings from the current machine
scripts/install.py       Install settings on another machine; dry-run by default
scripts/check-secrets.py Scan files for likely secrets before committing
tests/                   Tests for snapshot and deduplication behavior
private/                 Local private settings; gitignored and never committed
```

In `manifests/inventory.json`, `skills` lists the deduplicated skill names stored in this repository. `source_skills` records the local and symlinked skills found in each agent's source directory when the snapshot was created.

> `skills/hermes` excludes Hermes `.hub` indexes and caches, curator backups, and other runtime state. Codex's built-in `.system` skills are also excluded. Each tool should install or update those files itself.

## Capture settings from the current machine

```bash
python3 scripts/snapshot.py
python3 scripts/check-secrets.py
```

To update only configs and the inventory without copying skills again:

```bash
python3 scripts/snapshot.py --configs-only
```

`snapshot.py`:

1. Copies `~/.agents/skills` into `skills/shared`.
2. Captures non-symlinked, agent-specific skills. If a skill's frontmatter `name` already exists in shared, the agent-specific copy is removed even if its contents differ.
3. Promotes a skill to `skills/shared` when two or more agents have identical copies of the entire skill directory. Those agents use symlinks when the settings are installed.
4. Captures MCP and primary agent settings.
5. Replaces sensitive values with `${ENV_VAR}` references and rewrites the current home directory as `~`.

The sanitizer is a safety check, not a complete secret-management system. Always run `check-secrets.py` and review the diff before committing.

## Sync updates from a computer back to the repository

When an agent, MCP server, or skill changes on one computer, update the local repository before capturing that machine's state:

```bash
cd ~/Documents/GitHub/agent-air
git pull --rebase
python3 scripts/snapshot.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/check-secrets.py
git diff --check
git status --short
git diff
```

Review the diff for tokens, OAuth credentials, sessions, caches, and other machine-specific data. Then commit and push:

```bash
git add -A
git commit -m "chore: sync agent settings"
git push
```

### Updating a shared skill

After installation, shared skills are symlinks to `~/.agents/skills/<name>`. If an agent updates the target of that symlink, run `snapshot.py` to write the new version back to `skills/shared`.

Check whether a skill is still a symlink:

```bash
readlink ~/.claude/skills/<skill-name>
readlink ~/.codex/skills/<skill-name>
```

Some agent updaters may replace a symlink with a real directory. If shared already contains a skill with the same name, `skills/shared` remains canonical. Compare the versions and copy the version you want to keep into `~/.agents/skills/<skill-name>` before taking a snapshot:

```bash
diff -ru ~/.agents/skills/<skill-name> ~/.claude/skills/<skill-name>

# Run this only after confirming that the Claude version should replace shared.
rsync -a --delete \
  ~/.claude/skills/<skill-name>/ \
  ~/.agents/skills/<skill-name>/

python3 scripts/snapshot.py
```

Do not use `rsync --delete` before reviewing the diff. If both same-name versions must remain available, change the frontmatter `name` of one skill so it becomes a distinct agent-specific skill.

## Install on another computer

Pull the latest repository changes, then run the installer without `--apply` to preview its work:

```bash
cd ~/Documents/GitHub/agent-air
git pull --rebase
python3 scripts/install.py
```

Install skills after reviewing the dry-run:

```bash
python3 scripts/install.py --apply
```

Install sanitized configs as well:

```bash
python3 scripts/install.py --configs --apply
```

The installer backs up replaced paths as `*.agent-air.bak`. Shared skills are installed in `~/.agents/skills`, and each agent uses relative symlinks to those canonical copies. If the repository still contains a duplicate agent-specific copy, the installer stops and asks you to run `snapshot.py` first. Hermes-specific skills and shared symlinks are installed together.

## Secrets and private settings

### Reference environment variables from public configs

Hermes MCP supports both `${VAR}` and `${env:VAR}`:

```yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

For an HTTP MCP server:

```yaml
mcp_servers:
  internal:
    url: https://mcp.example.com/mcp
    headers:
      Authorization: "Bearer ${INTERNAL_MCP_TOKEN}"
```

Hermes reads secrets from `~/.hermes/.env`, or from the active profile's `.env` when profiles are enabled. Do not commit that file.

### OAuth MCP servers

Do not copy tokens for servers configured with `auth: oauth`. Hermes stores those tokens in `~/.hermes/mcp-tokens/<server>.json`. Authorize the server again on a new computer:

```bash
hermes mcp login <server>
```

### Can an agent read a gitignored config file?

Yes. `.gitignore` controls Git tracking, not filesystem access. An agent can still read files under `private/` through file tools, shell commands, or scripts when its sandbox and approval policy allow it.

Suggested layout:

```text
private/
  hermes.env
  cursor.mcp.local.json
```

- `private/` is ignored by Git.
- Verify the rule with `git check-ignore -v private/hermes.env`.
- Do not paste secrets into `AGENTS.md`, skills, or prompts.
- Do not treat `.gitignore` as a security boundary. If an agent must not see a secret, use macOS Keychain, 1Password CLI, an access-controlled wrapper, or MCP OAuth, and inject the secret only at runtime.

Create a local environment file:

```bash
mkdir -p private
cp .env.example private/hermes.env
chmod 600 private/hermes.env
```

## Validation

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/check-secrets.py
python3 scripts/install.py
git diff --check
git status --short
```

Verify ignore rules:

```bash
git check-ignore -v private/hermes.env .env
```

## Current Hermes MCP servers

The current Hermes MCP servers use OAuth, so this repository stores only their server URLs and `auth: oauth` settings:

- Atlassian
- Context7
- Figma

OAuth tokens are not stored in this repository. Authorize each server again on a new computer.
