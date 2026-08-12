#!/usr/bin/env python3
"""Snapshot local agent settings into this repository without committing secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()

SKILL_SOURCES = {
    "shared": HOME / ".agents" / "skills",
    "hermes": HOME / ".hermes" / "skills",
    "claude": HOME / ".claude" / "skills",
    "codex": HOME / ".codex" / "skills",
    "cursor": HOME / ".cursor" / "skills",
    "opencode": HOME / ".config" / "opencode" / "skills",
    "gemini": HOME / ".gemini" / "skills",
}

CONFIG_SOURCES = {
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

# Provider-managed/internal directories are intentionally not copied.
SKILL_EXCLUDES = {
    "hermes": {".curator_backups", ".hub"},
    "codex": {".system"},
}

SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(token|secret|password|passwd|api[_-]?key|private[_-]?key|access[_-]?key|client[_-]?secret)(?:$|[_-])",
    re.IGNORECASE,
)
KNOWN_SECRET_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}"),
    re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]
PLACEHOLDER = re.compile(r"\$\{(?:env:)?[A-Za-z_][A-Za-z0-9_]*\}")


def server_name(path: tuple[str, ...]) -> str:
    for marker in ("mcpServers", "mcp_servers", "mcp"):
        if marker in path:
            index = path.index(marker)
            if index + 1 < len(path):
                return path[index + 1]
    return "MCP"


def env_name(path: tuple[str, ...], key: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").upper()
    if cleaned in {"AUTHORIZATION", "AUTH"}:
        cleaned = "TOKEN"
    if cleaned.startswith("X_"):
        cleaned = cleaned[2:]
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", server_name(path)).strip("_").upper()
    if prefix and not cleaned.startswith(prefix + "_"):
        cleaned = prefix + "_" + cleaned
    return cleaned or "MCP_SECRET"


def is_sensitive_key(key: str, path: tuple[str, ...]) -> bool:
    lower = key.lower()
    if lower in {"authorization", "proxy-authorization"}:
        return True
    if "headers" in (part.lower() for part in path) and ("token" in lower or "key" in lower or "auth" in lower):
        return True
    if "env" in (part.lower() for part in path) and SENSITIVE_KEY.search(key):
        return True
    return bool(SENSITIVE_KEY.search(key))


def redact_scalar(value: Any, variable: str, key: str) -> Any:
    if value in (None, ""):
        return value
    if isinstance(value, str) and PLACEHOLDER.search(value):
        return value
    placeholder = "${" + variable + "}"
    if key.lower() in {"authorization", "proxy-authorization"}:
        return "Bearer " + placeholder
    return placeholder


def sanitize_json(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            child_path = path + (str(key),)
            if is_sensitive_key(str(key), path):
                result[key] = redact_scalar(child, env_name(path, str(key)), str(key))
            else:
                result[key] = sanitize_json(child, child_path)
        return result
    if isinstance(value, list):
        return [sanitize_json(item, path) for item in value]
    if isinstance(value, str):
        return sanitize_known_patterns(value)
    return value


def sanitize_known_patterns(text: str) -> str:
    for pattern in KNOWN_SECRET_PATTERNS:
        text = pattern.sub("${REDACTED_SECRET}", text)
    text = text.replace(str(HOME), "~")
    return text


def sanitize_text(text: str) -> str:
    """Best-effort sanitizer for YAML/TOML/JSONC while preserving formatting."""
    output = []
    section = "MCP"
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        section_match = re.match(r"\[(?:mcp_servers\.)?([^\].]+)", stripped)
        if section_match:
            section = section_match.group(1).strip('"')
        pair = re.match(r"^(\s*)([A-Za-z0-9_.\-\"']+)(\s*[:=]\s*)(.*?)(\r?\n)?$", line)
        if pair:
            indent, raw_key, separator, raw_value, newline = pair.groups()
            key = raw_key.strip('"\'')
            if is_sensitive_key(key, ("mcp_servers", section)) and not PLACEHOLDER.search(raw_value):
                variable = env_name(("mcp_servers", section), key)
                replacement = "Bearer ${%s}" % variable if key.lower() == "authorization" else "${%s}" % variable
                quote = '"' if separator.strip() == "=" or raw_value.lstrip().startswith('"') else ""
                line = f"{indent}{raw_key}{separator}{quote}{replacement}{quote}{newline or ''}"
        output.append(sanitize_known_patterns(line))
    return "".join(output)


def safe_copy_tree(source: Path, destination: Path, excludes: set[str]) -> tuple[int, int]:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    file_count = 0
    byte_count = 0
    for child in sorted(source.iterdir(), key=lambda p: p.name):
        if child.name.startswith(".") or child.name in excludes or child.is_symlink() or not child.is_dir():
            continue
        target = destination / child.name
        shutil.copytree(
            child,
            target,
            symlinks=False,
            ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", "node_modules", ".git"),
        )
        for file in target.rglob("*"):
            if file.is_file():
                file_count += 1
                byte_count += file.stat().st_size
    return file_count, byte_count


def declared_skill_name(skill_file: Path) -> str:
    text = skill_file.read_text(errors="replace")[:5000]
    match = re.search(r"(?m)^name:\s*[\"']?([^\"'\n]+)", text)
    return match.group(1).strip() if match else skill_file.parent.name


def remove_shared_duplicates(destination: Path, shared_names: set[str]) -> list[str]:
    """Remove agent-specific skill roots whose declared name exists in shared."""
    removed = []
    skill_files = sorted(destination.rglob("SKILL.md"), key=lambda p: len(p.parts), reverse=True)
    for skill_file in skill_files:
        if not skill_file.exists():
            continue
        name = declared_skill_name(skill_file)
        if name not in shared_names:
            continue
        shutil.rmtree(skill_file.parent)
        removed.append(name)
    for directory in sorted(
        (path for path in destination.rglob("*") if path.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        if not any(directory.iterdir()):
            directory.rmdir()
    return removed


def skill_tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: str(p.relative_to(root))):
        if not path.is_file() or path.is_symlink():
            continue
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def consolidate_duplicate_skills(skills_root: Path) -> list[str]:
    """Make shared canonical and promote identical cross-agent skill copies."""
    shared = skills_root / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    shared_names = {
        declared_skill_name(path)
        for path in shared.rglob("SKILL.md")
    }

    # An existing shared skill always wins over agent-specific copies/variants.
    for agent_dir in sorted(skills_root.iterdir(), key=lambda p: p.name):
        if not agent_dir.is_dir() or agent_dir.name == "shared":
            continue
        remove_shared_duplicates(agent_dir, shared_names)

    by_name: dict[str, list[Path]] = {}
    for agent_dir in sorted(skills_root.iterdir(), key=lambda p: p.name):
        if not agent_dir.is_dir() or agent_dir.name == "shared":
            continue
        for skill_file in agent_dir.rglob("SKILL.md"):
            by_name.setdefault(declared_skill_name(skill_file), []).append(skill_file.parent)

    promoted = []
    for name, copies in sorted(by_name.items()):
        if len(copies) < 2:
            continue
        digests = {skill_tree_digest(path) for path in copies}
        if len(digests) != 1:
            continue
        folder_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-") or copies[0].name
        destination = shared / folder_name
        if destination.exists():
            raise RuntimeError(f"Cannot promote {name}: shared destination already exists: {destination}")
        shutil.copytree(copies[0], destination)
        for copy in copies:
            shutil.rmtree(copy)
        promoted.append(name)

    for agent_dir in sorted(skills_root.iterdir(), key=lambda p: p.name):
        if not agent_dir.is_dir() or agent_dir.name == "shared":
            continue
        for directory in sorted(
            (path for path in agent_dir.rglob("*") if path.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()
    return promoted


def write_config(relative: str, source: Path) -> bool:
    if not source.exists():
        return False
    destination = REPO / "configs" / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(errors="replace")
    if source.suffix == ".json":
        try:
            data = json.loads(text)
            text = json.dumps(sanitize_json(data), indent=2, ensure_ascii=False) + "\n"
        except json.JSONDecodeError:
            text = sanitize_text(text)
    else:
        text = sanitize_text(text)
    destination.write_text(text)
    return True


def inventory() -> dict[str, Any]:
    result: dict[str, Any] = {"skills": {}, "source_skills": {}, "configs": []}
    for name, root in SKILL_SOURCES.items():
        if not root.exists():
            continue
        local = []
        links = []
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            if child.name.startswith("."):
                continue
            if child.is_symlink():
                links.append(child.name)
            elif child.is_dir():
                local.append(child.name)
        result["source_skills"][name] = {"local": local, "symlinked": links}
    skills_root = REPO / "skills"
    if skills_root.exists():
        for agent_dir in sorted(skills_root.iterdir(), key=lambda p: p.name):
            if not agent_dir.is_dir():
                continue
            result["skills"][agent_dir.name] = sorted(
                declared_skill_name(path)
                for path in agent_dir.rglob("SKILL.md")
            )
    for relative, source in CONFIG_SOURCES.items():
        if source.exists():
            result["configs"].append(relative)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs-only", action="store_true", help="Do not recopy skill trees")
    args = parser.parse_args()

    copied = []
    if not args.configs_only:
        shared_names = {
            declared_skill_name(path)
            for path in SKILL_SOURCES["shared"].rglob("SKILL.md")
        }
        for name, source in SKILL_SOURCES.items():
            if not source.exists():
                continue
            safe_copy_tree(source, REPO / "skills" / name, SKILL_EXCLUDES.get(name, set()))
            if name != "shared":
                destination = REPO / "skills" / name
                removed = remove_shared_duplicates(destination, shared_names)
                if removed:
                    print(f"skills/{name}: removed shared duplicates: {', '.join(sorted(set(removed)))}")
        promoted = consolidate_duplicate_skills(REPO / "skills")
        if promoted:
            print(f"skills/shared: promoted identical cross-agent skills: {', '.join(promoted)}")
        for name in SKILL_SOURCES:
            destination = REPO / "skills" / name
            if not destination.exists():
                continue
            files = [path for path in destination.rglob("*") if path.is_file()]
            copied.append((name, len(files), sum(path.stat().st_size for path in files)))

    config_count = sum(write_config(relative, source) for relative, source in CONFIG_SOURCES.items())
    manifest_dir = REPO / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "inventory.json").write_text(
        json.dumps(inventory(), indent=2, ensure_ascii=False) + "\n"
    )

    for name, files, size in copied:
        print(f"skills/{name}: {files} files, {size} bytes")
    print(f"configs: {config_count} sanitized files")
    print("Secrets were replaced with ${ENV_VAR} placeholders; run scripts/check-secrets.py next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
