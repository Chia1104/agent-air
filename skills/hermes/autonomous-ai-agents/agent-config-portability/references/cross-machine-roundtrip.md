# Cross-Machine Round Trip

Use this workflow when one computer has newer agent skills or settings and the portability repo must become the new source of truth.

## Publish local changes

1. Update the repo before snapshotting so another machine's commit is not overwritten:

   ```bash
   git pull --rebase
   ```

2. Determine whether an updated shared skill is still a symlink into the canonical local shared tree:

   ```bash
   readlink ~/.claude/skills/<skill-name>
   readlink ~/.codex/skills/<skill-name>
   ```

3. If it still resolves into `~/.agents/skills/<skill-name>`, snapshot normally.
4. If an agent updater replaced the symlink with a real directory while shared already has that declared name, compare the trees first. The shared tree remains canonical, so explicitly copy the chosen new version into `~/.agents/skills/<skill-name>` before snapshotting. Do not let snapshot order silently choose a winner.
5. Run the repository's snapshot, tests, secret scan, syntax/diff checks, and inspect the diff.
6. Commit and push only after confirming no credentials, OAuth stores, sessions, caches, or machine paths entered the diff.

Generic sequence:

```bash
git pull --rebase
python3 scripts/snapshot.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/check-secrets.py
git diff --check
git status --short
git diff
git add -A
git commit -m "chore: sync agent settings"
git push
```

## Apply on another computer

```bash
git pull --rebase
python3 scripts/install.py          # dry-run
python3 scripts/install.py --apply  # skills
```

Install sanitized configs only as a distinct, intentional operation, for example `python3 scripts/install.py --configs --apply`. OAuth and ignored private values must be restored or reauthenticated separately.

## Conflict policy

- Existing shared declared name: shared wins; reconcile an updater-created local directory into shared explicitly.
- Same declared name, divergent trees, no shared canonical copy: do not auto-merge or discard either version.
- Identical trees used by two or more agents: promote one copy to shared and link consumers to it.
- Both divergent variants are genuinely needed: rename one skill's declared frontmatter `name` so identity and installation behavior are explicit.

Never use destructive synchronization such as `rsync --delete` until a recursive diff has been reviewed.