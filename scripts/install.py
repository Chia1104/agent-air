#!/usr/bin/env python3
"""Install repository-managed agent settings into the current home directory."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()
SHARED_TARGET = HOME / ".agents" / "skills"
AGENT_SKILL_TARGETS = {
    "claude": HOME / ".claude" / "skills",
    "codex": HOME / ".codex" / "skills",
    "cursor": HOME / ".cursor" / "skills",
    "opencode": HOME / ".config" / "opencode" / "skills",
    "gemini": HOME / ".gemini" / "skills",
    "hermes": HOME / ".hermes" / "skills",
}
CONFIG_TARGETS = {
    "hermes/config.yaml": HOME / ".hermes" / "config.yaml",
    "hermes/SOUL.md": HOME / ".hermes" / "SOUL.md",
    "claude/settings.json": HOME / ".claude" / "settings.json",
    "claude/mcp.json": HOME / ".claude" / ".mcp.json",
    "codex/config.toml": HOME / ".codex" / "config.toml",
    "codex/AGENTS.md": HOME / ".codex" / "AGENTS.md",
    "codex/hooks.json": HOME / ".codex" / "hooks.json",
    "cursor/mcp.json": HOME / ".cursor" / "mcp.json",
    "cursor/hooks.json": HOME / ".cursor" / "hooks.json",
    "opencode/opencode.json": HOME / ".config" / "opencode" / "opencode.json",
    "opencode/opencode.jsonc": HOME / ".config" / "opencode" / "opencode.jsonc",
    "opencode/AGENTS.md": HOME / ".config" / "opencode" / "AGENTS.md",
    "gemini/settings.json": HOME / ".gemini" / "settings.json",
    "gemini/GEMINI.md": HOME / ".gemini" / "GEMINI.md",
    "shared/skill-lock.json": HOME / ".agents" / ".skill-lock.json",
    "shared/marketplace.json": HOME / ".agents" / "plugins" / "marketplace.json",
}


def declared_skill_name(skill_file: Path) -> str:
    text = skill_file.read_text(errors="replace")[:5000]
    match = re.search(r"(?m)^name:\s*[\"']?([^\"'\n]+)", text)
    return match.group(1).strip() if match else skill_file.parent.name


def shared_skill_names() -> set[str]:
    return {
        declared_skill_name(path)
        for path in (REPO / "skills" / "shared").rglob("SKILL.md")
    }


def validate_no_shared_duplicates() -> None:
    shared = shared_skill_names()
    duplicates = []
    for agent_dir in sorted((REPO / "skills").iterdir(), key=lambda p: p.name):
        if not agent_dir.is_dir() or agent_dir.name == "shared":
            continue
        for skill_file in agent_dir.rglob("SKILL.md"):
            name = declared_skill_name(skill_file)
            if name in shared:
                duplicates.append(f"{agent_dir.name}:{name} ({skill_file.parent.relative_to(REPO)})")
    if duplicates:
        details = "\n  ".join(duplicates)
        raise SystemExit(
            "Duplicate skills also exist in shared; run scripts/snapshot.py to remove them:\n  "
            + details
        )


def backup(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    backup_path = path.with_name(path.name + ".agent-air.bak")
    if backup_path.exists() or backup_path.is_symlink():
        if backup_path.is_dir() and not backup_path.is_symlink():
            shutil.rmtree(backup_path)
        else:
            backup_path.unlink()
    shutil.move(str(path), str(backup_path))
    print(f"backup: {path} -> {backup_path}")


def replace_tree(source: Path, target: Path, dry_run: bool) -> None:
    print(f"copy tree: {source} -> {target}")
    if dry_run:
        return
    backup(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def overlay_tree(source: Path, target: Path, dry_run: bool) -> None:
    if not source.exists():
        return
    for child in sorted(source.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        destination = target / child.name
        print(f"copy skill: {child} -> {destination}")
        if dry_run:
            continue
        target.mkdir(parents=True, exist_ok=True)
        backup(destination)
        shutil.copytree(child, destination)


def install_shared_links(agent: str, target: Path, dry_run: bool) -> None:
    source = REPO / "skills" / "shared"
    if not source.exists():
        return
    for skill in sorted(source.iterdir(), key=lambda p: p.name):
        if not skill.is_dir():
            continue
        link = target / skill.name
        relative = os.path.relpath(SHARED_TARGET / skill.name, start=target)
        print(f"link [{agent}]: {link} -> {relative}")
        if dry_run:
            continue
        target.mkdir(parents=True, exist_ok=True)
        if link.exists() or link.is_symlink():
            if link.is_symlink() and link.resolve() == (SHARED_TARGET / skill.name).resolve():
                continue
            backup(link)
        link.symlink_to(relative, target_is_directory=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Perform writes; default is dry-run")
    parser.add_argument("--configs", action="store_true", help="Also install sanitized configs (requires secrets in environment/private files)")
    args = parser.parse_args()
    dry_run = not args.apply
    validate_no_shared_duplicates()

    replace_tree(REPO / "skills" / "shared", SHARED_TARGET, dry_run)
    for agent, target in AGENT_SKILL_TARGETS.items():
        overlay_tree(REPO / "skills" / agent, target, dry_run)
        install_shared_links(agent, target, dry_run)

    if args.configs:
        for relative, target in CONFIG_TARGETS.items():
            source = REPO / "configs" / relative
            if not source.exists():
                continue
            print(f"copy config: {source} -> {target}")
            if dry_run:
                continue
            backup(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    print("dry-run complete; add --apply to write changes." if dry_run else "install complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
