# Removing a Node version manager (nvm etc.) after switching to another one (e.g. Vite+ `vp`)

Case: user moved Node/package-manager management to a new tool and asks "can I remove nvm now?". Answer "yes, after migrating globals" and do it in this order.

1. **Confirm the replacement owns PATH.** `which -a node npm pnpm` and `vp env doctor` (or the new tool's doctor). Note other Node copies that are NOT the manager's (e.g. Hermes' own `~/.hermes/node`, `~/.local/bin/node` symlinks) and say they are unaffected.
2. **Inventory the old manager's global packages per version**, not just the default: `ls ~/.nvm/versions/node/*/lib/node_modules` (skip `npm`, `corepack`). Scoped packages live one level deeper (`@scope/pkg`) — `ls` the `@scope` dir; an empty scope dir is a leftover, ignore it. Deleting the manager deletes these, so they must be reinstalled first.
   - Read versions with the manager's own node in a loop only if needed; a naive `node -p require(...)` with a relative path fails — use absolute paths or skip versions, the package names are what matter.
3. **Show the user the table (version -> globals) and ask which to keep** unless they already said "all handled". Old duplicates across versions collapse into one reinstall. Scoped packages whose purpose is unclear: reinstall the ones that expose a known binary (check `<version>/bin` for symlinks, e.g. `pi`), and list the rest as not reinstalled.
4. **Reinstall with the new tool from `~`**: `vp install -g <pkgs>` then `vp list -g` to confirm; bins land in `~/.local/share/vite-plus/bin`.
5. **Edit the rc file**: back up (`cp ~/.zshrc ~/.zshrc.bak-nvm`), remove the whole NVM block (NVM_DIR export, default-version PATH prepend, lazy-load `nvm()` function) with a small python slice between the block's header and last line rather than line-number `sed` (line numbers drift). Keep unrelated lines that sat inside the block (e.g. a `PNPM_HOME` PATH prepend) and re-title the section. `zsh -n ~/.zshrc` for syntax, `diff` vs. backup.
6. **`rm -rf ~/.nvm`** (multi-GB), then verify with `zsh -ic 'which node pnpm <each global bin>; node -v; type nvm'` — every path should point into the new manager's bin dir and `nvm` should be not found. Also `brew list | grep nvm`.
7. Report: space freed, globals reinstalled, globals NOT reinstalled (so the user can add them), backup name, and "open a new shell / `exec zsh`" since old terminals carry the old PATH.

Related rc cleanups the user often asks next: alias wrappers such as `alias npm="sfw npm"` — back up, `sed -i '' '/sfw/d'`, diff, then offer to remove the now-empty `# aliases` header.
