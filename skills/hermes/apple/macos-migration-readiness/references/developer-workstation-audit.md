# Developer Workstation Audit Matrix

Use this reference with the `macos-migration-readiness` workflow. Commands are discovery-oriented; avoid starting services or revealing secret contents during a read-only audit.

## Audit Matrix

| Area | Evidence to collect | Preserve or rebuild? |
|---|---|---|
| Time Machine | destination, latest backup, ability to open restored files | Preserve and verify off-device |
| Desktop/Documents | size, cloud-management flags, symlink/real path | Preserve local-only data |
| Applications | name, version, bundle ID, install source | Reinstall |
| Homebrew | taps, requested formulae, casks, services, Brewfile | Reinstall; preserve service data separately |
| Git | path, branch, remote, dirty state, ahead count | Preserve dirty/ahead/local-only repos |
| SSH/GPG | key filenames, config presence, known_hosts | Preserve encrypted; never print private keys |
| Apple signing | identity count/labels, provisioning profile count | Export private identities if needed |
| Mobile signing | `.p8`, `.p12`, `.jks`, `upload.keystore` | Preserve encrypted with passwords/IDs elsewhere |
| Containers | context, containers, volumes, mounts, storage size | Logical DB export; rebuild images/cache |
| Local databases | engine/version, data location, service state | Logical export and restore test |
| IDEs/editors | settings, keybindings, extensions, sync state | Preserve settings; rebuild indexes/runtime downloads |
| Browser/API clients | sync account, local-only workspace, export status | Verify vendor sync; export local-only data |
| Cloud drives | provider root, client installed, sync/web verification | Verify remotely; placeholders are not backups |
| Agent tools | config, secrets, state DB, skills, sessions | Preserve encrypted; reinstall runtime |
| Login behavior | login items, LaunchAgents, default browser, permissions | Reconfigure |

## Useful Discovery Patterns

Prefer structured outputs and bounded scans. Adapt paths to the active user.

### System and backup

```bash
sw_vers
system_profiler SPHardwareDataType
fdesetup status
tmutil destinationinfo
tmutil latestbackup
profiles status -type enrollment
```

Do not copy hardware serial numbers, UUIDs, or provisioning UDIDs into the user-facing report.

### Applications

Read `Contents/Info.plist` from top-level apps under `/Applications` and `~/Applications`. Capture:

- `CFBundleDisplayName` / `CFBundleName`
- `CFBundleShortVersionString`
- `CFBundleIdentifier`

Exclude built-in system applications from the manual reinstall queue. Use App Store receipts or `mas list` when available; receipt detection only proves currently installed App Store apps, not the user's whole purchase history.

### Homebrew

```bash
brew tap
brew leaves --installed-on-request
brew list --cask
brew services list
brew bundle dump --force --file=/path/to/Brewfile
brew bundle check --verbose --file=/path/to/Brewfile
```

If `brew bundle check` reports that a present package "needs to be installed or updated," compare with `brew outdated`. That result does not by itself invalidate the generated Brewfile. Third-party taps should be reviewed before explicit trust is granted.

### Git recoverability scan

Walk likely project roots while pruning `node_modules`, build outputs, vendor directories, package stores, IDE indexes, and `.git` internals. For each repo collect:

```bash
git -C <repo> branch --show-current
git -C <repo> remote get-url origin
git -C <repo> status --porcelain
git -C <repo> rev-list --count '@{u}..HEAD'
```

Classify as P0 when any is true:

- working tree is dirty
- branch is ahead of upstream
- no origin remote exists
- remote access cannot be verified
- repo contains release signing assets or local environment data not committed by design

Do not automatically commit or push during an audit.

### Signing and secrets

```bash
security find-identity -v -p codesigning
```

Count provisioning profiles in both historical and current Xcode locations. Search likely user/project roots for signing artifacts, while pruning caches:

- `*.p8`, `*.p12`, `*.mobileprovision`
- `*.jks`, `*.keystore`, especially `upload.keystore`
- VPN profiles such as `*.ovpn`

Only report path and handling requirement. Recommend export of Apple signing identities with their private keys to encrypted `.p12` when reissuance is undesirable.

### Containers and databases

```bash
docker context show
docker system df
docker ps -a
docker volume ls
docker inspect <containers>
```

Map named volumes to container destinations. Build cache and images are usually rebuildable. Database volumes require a logical dump. When containers are stopped, leave them stopped during the audit unless the user asked to perform the backup.

### Runtime/cache classification

Break down these common large directories before recommending backup:

- `~/.nvm`, `~/.rustup`, `~/.cargo`, `~/go/pkg`
- `~/Library/pnpm`, `~/.bun`, `~/.gradle`, `~/.pub-cache`
- Android SDK and `~/.android/avd`
- IDE/editor Application Support directories
- Ollama/model stores

Keep manifests, version lists, settings, custom source, and desired emulator state. Re-download caches and SDK artifacts where practical.

### App-specific state

Check for settings and user data without assuming sync:

- Cursor/VS Code: settings, keybindings, snippets, extension list; large workspace/global storage may be disposable
- Zed: settings, extensions, optional agent threads
- JetBrains: Settings Sync, DataGrip data sources, local consoles, Keychain-backed passwords
- Postman/API clients: local workspaces, collections, environments, explicit export
- browsers: profile sync, bookmarks export, password sync
- launchers: vendor sync/export
- VPN/proxy tools: profiles, certificates, trusted root CA reinstallation
- messaging apps: mobile/cloud recovery path

If privacy permissions block a profile directory, add a manual sync/export checklist item instead of claiming it is empty.

## Artifact Layout

```text
Mac-reset-audit-YYYY-MM-DD/
├── README.md
├── Brewfile
├── app-inventory.csv
├── runtime-inventory.md
└── <editor>-extensions.txt
```

A good `README.md` starts with blockers, not inventory. It should name exact risky paths but never secret contents. Keep installation details in machine-readable side files so the checklist remains readable.

## Restore Order Rationale

1. Apple account, OS updates, FileVault/Find My
2. Password manager and recovery access
3. Xcode/Command Line Tools
4. Homebrew and package manifests
5. shell/dotfiles and SSH
6. language runtimes and SDKs
7. applications
8. projects and logical database restores
9. cloud/app sign-ins, permissions, login items, defaults
10. build/sign/auth/restore verification

This order minimizes the chance that the user restores secrets into an untrusted or incomplete base system and makes developer tooling dependencies available before project verification.

## Final Archive Verification

Validate all expected files, parse CSV, deduplicate extension lists, assert that every discovered P0 item appears in the README, create a zip, and run an archive integrity test. Deliver both the human-readable README and the complete archive when the chat platform supports native files.
