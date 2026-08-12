# Shared Skill Deduplication

## Policy

`skills/shared` is canonical. Compare skills by the `name` field in each `SKILL.md` frontmatter. If a shared name appears anywhere under an agent-specific tree, remove that entire skill root even if its contents differ.

## Deterministic algorithm

1. Recursively find `skills/shared/**/SKILL.md`.
2. Parse each declared `name`; fall back to the parent directory only when frontmatter is missing.
3. Recursively find `skills/<agent>/**/SKILL.md`.
4. For each matching declared name, remove the parent directory containing that `SKILL.md`.
5. Remove empty category directories from deepest to shallowest.
6. Build the post-dedup manifest from the repository tree, not from the original source tree.
7. Keep source layout under a separately named manifest field such as `source_skills`.

Do not use content hashes as the policy. Hashes are useful for reporting identical versus modified copies, but a modified variant still loses when shared is authoritative.

## Installer guard

Before any write:

- Build the set of shared declared names.
- Scan every agent-specific `SKILL.md` recursively.
- If any name intersects, stop with a list of agent, name, and path.
- Direct the operator to rerun the snapshot/dedup command.

Then install shared once and link each shared top-level skill into every agent. Preserve only unique agent-specific skills as real directories.

## Isolated verification

Use a temporary HOME or equivalent isolated destination and perform a real install, not only dry-run. Assert that:

- representative duplicates are symlinks into the canonical shared tree;
- representative unique agent skills are real directories;
- nested shared skills are reachable under the naming/layout expected by the target agent;
- the installer exits successfully;
- a repository scan reports zero shared/agent duplicate names.

## Common bug

If snapshot output reports pre-dedup file counts, operators may think duplicates remain. Recompute counts and byte totals from each destination tree after removal.
