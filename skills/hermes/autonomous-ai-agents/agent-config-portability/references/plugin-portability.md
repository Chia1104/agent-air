# Plugin Portability

Use a manifest-first policy for cross-machine plugin sync. Third-party plugin installations are declarative dependencies; local custom plugins are source code. Download caches and runtime payloads are neither.

## What to preserve

### Claude Code

Build a normalized manifest from the native installation records and settings:

- plugin ID (`plugin@marketplace`)
- scope (`user`, `project`, or `local`)
- enabled state
- reported version
- Git commit SHA when available
- marketplace name and portable source (GitHub repo, URL, or intentional local path)

Strip install paths, install/update timestamps, checkout directories, catalog caches, MCP runtime details duplicated elsewhere, and credentials. `claude plugin list --json` is useful for verification, while `installed_plugins.json`, `known_marketplaces.json`, and `settings.json.enabledPlugins` provide reconstructable state.

Restore in this order:

1. add missing marketplaces;
2. install missing plugins;
3. apply disabled state (new installs are normally enabled);
4. verify with `claude plugin list --json`.

Use noninteractive installation flags where supported, but keep the repository installer dry-run by default because marketplace plugins may execute setup commands.

### Codex

Normalize `codex plugin list --json` into:

- plugin ID
- marketplace
- enabled state
- reported version
- `managed` flag

Do not rely on CLI list output alone. Codex may omit configured bundled plugins whose marketplace snapshot is not currently visible. Merge `[plugins."..."]` sections from `config.toml` into the manifest so the audit record includes them.

Mark OpenAI bundled/runtime marketplaces as managed (for example, `openai-bundled` and `openai-primary-runtime`). Record managed plugins for audit, but let Codex install them. Reinstall only missing non-managed plugins after marketplace/config restoration.

### Local custom plugins

Track small user-authored Hermes and OpenCode plugin trees as source code. Preserve executable code and manifests, but exclude:

- `node_modules`
- `.git`
- caches
- bytecode
- logs
- auth/session state
- generated downloads

Install local plugins by backing up each destination and copying the repository version atomically. An offline mode should restore only these local files and skip all marketplace/network commands.

## What not to version

Never copy whole plugin directories blindly. Typical nonportable trees include:

- Claude plugin cache and marketplace checkouts
- Codex `.plugin-appserver`, cache, and install staging
- Cursor plugin cache
- runtime-managed plugin bundles
- installation timestamps and machine-specific absolute paths
- OAuth tokens, plugin credentials, cookies, sessions, or auth databases

A useful check is that the portable plugin tree is measured in KB or small MB, not hundreds of MB copied from agent caches.

## Snapshot algorithm

1. Read native declarative records without printing credential values.
2. Normalize provider-specific fields into stable JSON manifests.
3. Merge secondary config sources when the provider CLI omits configured plugins.
4. Copy only approved local custom plugin source roots with explicit ignore rules.
5. Preserve the prior manifest if a provider CLI is unavailable or emits invalid JSON; do not overwrite it with an empty list.
6. Run secret scanning over manifests and copied source.
7. Assert no forbidden runtime/cache directory appears under the repository plugin tree.

## Installer behavior

- Default to dry-run and print every marketplace/plugin command.
- Require an explicit plugin flag before marketplace or network actions.
- Restore configs and marketplace declarations before installing plugins on a new machine.
- Skip already-installed plugin IDs.
- Skip provider-managed runtime plugins.
- Offer an offline mode that still restores local plugin source.
- Back up local plugin destinations before replacement.

Recorded versions are audit data unless the provider CLI supports an explicit version/ref pin. Do not claim exact reproducibility when the installer can only install the marketplace's current version.

## Verification

- Unit-test normalization to prove paths and timestamps are removed.
- Test that managed runtime plugins are not scheduled for installation.
- Test command planning with present and missing plugins.
- Run a real offline install into a temporary HOME and verify local plugin files land correctly.
- Verify no plugin cache is created during offline restore.
- Run a normal dry-run on the source machine; an already-satisfied machine should schedule no remote install commands.
- Parse all generated manifests as JSON and run the repository secret scanner.
