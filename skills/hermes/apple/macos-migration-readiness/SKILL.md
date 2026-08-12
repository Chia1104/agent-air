---
name: macos-migration-readiness
description: "Use when auditing a Mac before reset, erase, or migration."
version: 1.0.0
author: Hermes Agent
platforms: [macos]
metadata:
  hermes:
    tags: [macos, reset, migration, backup, workstation, audit]
---

# macOS Migration Readiness

Use this skill when a user plans to erase, reset, replace, or migrate a Mac and wants an evidence-backed list of what to back up, reinstall, and reconfigure. The deliverable is a verified artifact, not just chat advice.

## Core Principle

Treat the task as **recoverability analysis**, not an app inventory. Installed apps are usually reproducible; local source changes, signing keys, databases, cloud placeholders, recovery keys, and authentication state are not.

Never tell the user a Mac is ready to erase until every P0 item is either backed up and verified or explicitly accepted as disposable.

## Workflow

### 1. Establish live system and backup state

Collect, without exposing serial numbers in the report:

- macOS version, model/chip, memory, architecture
- FileVault and Activation Lock state
- Time Machine destinations and latest backup
- DEP/MDM enrollment
- available disk space
- whether Desktop and Documents are local, symlinked, or iCloud-managed
- cloud-storage providers and whether their client apps are present

A cloud-mounted directory is not proof of backup. Online-only files, stale sync, provider deadlocks, and placeholder files require verification from the provider web UI or another device.

### 2. Inventory reinstallable software

Capture separately:

- non-system `.app` bundles with version and bundle ID
- Mac App Store apps, preferably by receipt or `mas` when available
- Homebrew taps, requested formulae, casks, and services
- editor extensions
- language/runtime versions and version managers
- global CLI packages where meaningful
- login items and user LaunchAgents
- fonts

Generate a `Brewfile` when Homebrew is present. A failed `brew bundle check` can mean installed packages are merely outdated; run the verbose check before declaring the Brewfile invalid.

### 3. Find irreplaceable local data

Inspect top-level home data and then drill into large directories. Prioritize:

- Desktop, Documents, Downloads, project folders, media, and app project files
- Git repositories with dirty working trees, commits ahead of upstream, or no remote
- SSH/GPG keys and configs
- Apple code-signing identities and provisioning profiles
- Android release keystores (`upload.keystore`, `.jks`) and APNs/API private keys (`.p8`, `.p12`)
- VPN profiles and client certificates
- password-manager recovery material
- local databases, Docker/OrbStack volumes, VM disks, and unsynced app workspaces
- agent configuration/state directories such as `~/.hermes`

Do not print secret contents. Record only existence, count, safe path, and required handling.

### 4. Separate data from rebuildable caches

Large directories are not automatically backup priorities. Break them down enough to distinguish:

- **Preserve:** settings, keybindings, snippets, unsynced history, database dumps, emulator state if desired, custom source, credentials
- **Rebuild:** package stores, node_modules, Gradle caches, SDK downloads, IDE indexes, downloaded language servers, build caches, model blobs when easily re-pulled

For Git project trees, size alone is misleading: a 20 GB repo may be mostly `node_modules`, while one modified 2 KB config file is the real P0 item.

### 5. Assess application sync and export paths

For password managers, browsers, Postman/API clients, IDEs, database tools, launchers, chat apps, VPN tools, and cloud drives, distinguish:

- account-synced data
- local-only data
- data that needs an explicit export
- credentials stored only in Keychain
- settings that can be restored from dotfiles or vendor sync

If macOS privacy controls block inspection, record the limitation and require manual verification; do not infer that data is absent.

### 6. Handle databases safely

List container names, volume names, mounts, and size without mutating them. Prefer logical dumps (`pg_dump`, `pg_dumpall`, equivalent database-native export) over copying live volume directories. If services are stopped and the user only asked for an audit, do not start them silently; mark dump verification as a required follow-up.

### 7. Produce artifacts

Create one audit directory containing at least:

- `README.md` — prioritized P0/P1/P2 checklist
- `app-inventory.csv`
- `Brewfile` when applicable
- editor extension inventories
- `runtime-inventory.md`

The README should lead with blockers, then provide:

1. **P0 before erase** — backups, local changes, keys, DBs, cloud verification
2. **P1 reinstall order** — password manager, OS/Apple account, Xcode/CLT, Homebrew, runtimes, apps, data
3. **P2 reconfiguration** — accounts, permissions, login items, defaults, signing, VPN
4. **Final verification** — open files from backup, Git status, auth checks, build/sign tests, DB restore test
5. **Audit limitations** — privacy-denied paths, cloud state not proven, stopped services not inspected

Compress the directory and test the archive before delivery.

## Verification Gates

Before finishing:

- all artifact files exist and are non-empty
- CSV parses and has the expected headers
- extension lists are deduplicated
- README mentions every P0 discovery
- archive extraction test passes
- no secret values, private-key contents, tokens, recovery codes, serial numbers, or raw Keychain data appear in deliverables
- report clearly says not to erase until backups are off-device and verified

## Pitfalls

- **App-list tunnel vision:** applications are the easy part; credentials and local state are the risk.
- **Cloud equals backup:** a sync directory may contain placeholders or unsynced changes.
- **Dirty Git omission:** scan status, upstream ahead count, and missing remotes, not just repo names.
- **Copying caches wholesale:** package stores and IDE indexes inflate backup size and restore complexity.
- **Copying database volumes blindly:** use logical exports and test a restore.
- **Trusting a generated Brewfile without review:** third-party taps may require explicit trust; review before `brew trust`.
- **Leaking secrets into the report:** paths and counts are enough.
- **Claiming completeness after permission errors:** surface the limitation and give a manual verification item.
- **Producing only prose:** save reusable inventories and verify the archive.

## Supporting Reference

See `references/developer-workstation-audit.md` for a detailed audit matrix, command patterns, and classification guidance for developer Macs.
