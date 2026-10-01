---
name: local-tool-uninstall
description: Use when removing a CLI/agent/dev tool from the Mac.
---

# Local tool uninstall (macOS)

Class of task: "how do I remove X", "clean out these agents/tools", "what agent folders are on this machine". Detects install method, removes binary, config, data, caches and PATH lines, then verifies. Answer in the user's language (Traditional Chinese for this user), short, table/list form.

## Procedure

1. **Find how it was installed before deleting anything.** One read-only call:
   `which -a <tool>`; `brew list | grep -i <tool>`; `npm ls -g --depth=0 | grep -i <tool>`; `uv tool list`; `pipx list`; `grep -n <tool> ~/.zshrc ~/.zprofile ~/.zshenv ~/.bashrc`; `ls /Applications | grep -i <tool>`.
   The binary path tells the method: `~/.<tool>/bin` = curl install script (delete the dir + the PATH line it appended to `.zshrc`); `/opt/homebrew` or `/usr/local` = brew (`brew uninstall`, `--cask` for apps); `.nvm/.../bin` = npm -g (`npm uninstall -g`); `uv tool` = `uv tool uninstall`.
2. **Answer "is deleting `~/.<tool>` enough?" with the full location list.** The dotfolder is often only the binary; user data lives elsewhere. Check:
   `~/.config/<t>`, `~/.local/share/<t>`, `~/.local/state/<t>`, `~/.cache/<t>`, `~/Library/Application Support/<t>` (case varies, e.g. `orca`), `~/Library/{Caches,Preferences,Logs,Saved Application State}/*<t>*`, `~/Library/Preferences/com.<vendor>.<t>.plist`.
   Credentials/sessions live in `~/.local/share/<t>` or the tool's own dotfolder — say so and offer a backup before deleting.
3. **Before the delete call, one combined read-only scan**: sizes (`du -sh`), leftover locations above, running processes (`ps aux | grep -iE`), references in shell rc files and other tools' configs (`~/.hermes/config.yaml`, `~/.claude.json`, `~/.codex/config.toml`, `~/.cursor/mcp.json`), and `ls -A` of each target folder.
4. **Shared/mixed folders: inspect contents before `rm -rf`.** A folder named after tool A may hold tool B's data (e.g. `~/.gemini` also held Antigravity IDE profiles). Delete only files belonging to the named tool, report what remains and whose it is, and ask before removing the rest. Skill dirs under `~/.<tool>/skills` are often symlinks into `~/.agents/skills` — `rm -rf` removes the links only; confirm the source in `~/.agents/skills` is intact afterwards.
5. **Edit rc files safely**: `cp ~/.zshrc ~/.zshrc.bak-<tool>` first, delete only the tool's lines with `sed -i ''` (multi-line blocks: slice between header and last line in python; keep unrelated lines inside the block), then `zsh -n ~/.zshrc` and `diff` backup vs. new. Tell the user the backup exists so they can delete it.
6. **Delete, then verify in the same call**: `ls -d <every path>` should all say "No such file"; `zsh -ic 'which <tool> || echo not found'` for PATH; re-scan Library locations for stragglers (a `.plist` in `~/Library/Preferences` is commonly missed by the first pass).

## Special case: Node version managers

Removing nvm/fnm/etc. deletes every global npm package installed under it. Migrate those first — see `references/node-version-manager-migration.md`.

## User preferences

- Once the user says "直接幫我移除 / 清掉", run it without re-asking; still do the read-only scan first in the same step and report anything surprising afterwards.
- When the user later confirms a leftover ("也移除吧"), sweep that tool's remaining Library traces too, not just the one named folder.
- Final report: what was deleted (paths), what was kept and why, backup file names. No process narration.

## Pitfalls

- Security scanners flag bursts of `rm -rf` and multi-tool `for` loops; the approval prompt goes to the user — keep going once approved.
- "No executable + folder still present" means a leftover from an earlier uninstall or an app-bundled config, not a live install; list these separately from live tools when inventorying.
- Keyword-based inventory misses obscure tools; say so instead of claiming the list is complete.
- Do not delete `~/.agents` (shared skill store) or other tools' folders unless explicitly named.
