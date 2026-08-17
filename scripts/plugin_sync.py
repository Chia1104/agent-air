#!/usr/bin/env python3
"""Snapshot and restore declarative plugin state without copying caches."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

RUNTIME_NAMES = {
    ".plugin-appserver",
    ".remote-plugin-install-staging",
    "cache",
    "data",
    "marketplaces",
    "node_modules",
    "repos",
}
COPY_IGNORES = shutil.ignore_patterns(
    ".DS_Store",
    ".git",
    "__pycache__",
    "*.pyc",
    "cache",
    "node_modules",
)


def normalize_claude_plugins(
    installed: dict[str, Any],
    marketplaces: dict[str, Any],
    enabled_plugins: dict[str, Any],
) -> dict[str, Any]:
    plugins = []
    for plugin_id, records in sorted(installed.get("plugins", {}).items()):
        record = records[0] if records else {}
        plugin = {
            "id": plugin_id,
            "scope": record.get("scope", "user"),
            "version": record.get("version", "unknown"),
        }
        if record.get("gitCommitSha"):
            plugin["gitCommitSha"] = record["gitCommitSha"]
        plugin["enabled"] = bool(enabled_plugins.get(plugin_id, True))
        plugins.append(plugin)

    normalized_marketplaces = []
    for name, record in sorted(marketplaces.items()):
        source = record.get("source")
        if not isinstance(source, dict):
            continue
        normalized_marketplaces.append({"name": name, "source": source})

    return {
        "schemaVersion": 1,
        "plugins": plugins,
        "marketplaces": normalized_marketplaces,
    }


def normalize_codex_plugins(raw: dict[str, Any]) -> dict[str, Any]:
    plugins = []
    for record in sorted(raw.get("installed", []), key=lambda item: item.get("pluginId", "")):
        plugin_id = record.get("pluginId")
        if not plugin_id:
            continue
        marketplace = record.get("marketplaceName", "")
        plugins.append({
            "id": plugin_id,
            "version": record.get("version", "unknown"),
            "enabled": bool(record.get("enabled", True)),
            "marketplace": marketplace,
            "managed": marketplace.startswith("openai-") or marketplace.endswith("-runtime"),
        })
    return {"schemaVersion": 1, "plugins": plugins}


def merge_codex_config_plugins(manifest: dict[str, Any], config_text: str) -> dict[str, Any]:
    plugins = {
        plugin["id"]: dict(plugin)
        for plugin in manifest.get("plugins", [])
        if plugin.get("id")
    }
    section_pattern = re.compile(
        r'(?ms)^\[plugins\.(?:"([^"]+)"|([^\]]+))\]\s*(.*?)(?=^\[|\Z)'
    )
    for match in section_pattern.finditer(config_text):
        plugin_id = (match.group(1) or match.group(2)).strip()
        body = match.group(3)
        enabled_match = re.search(r"(?m)^enabled\s*=\s*(true|false)\s*$", body, re.IGNORECASE)
        enabled = enabled_match.group(1).lower() == "true" if enabled_match else True
        marketplace = plugin_id.rsplit("@", 1)[1] if "@" in plugin_id else ""
        record = plugins.get(plugin_id, {
            "id": plugin_id,
            "version": "unknown",
            "marketplace": marketplace,
            "managed": marketplace.startswith("openai-") or marketplace.endswith("-runtime"),
        })
        record["enabled"] = enabled
        plugins[plugin_id] = record
    return {"schemaVersion": 1, "plugins": [plugins[key] for key in sorted(plugins)]}


def copy_local_plugins(source: Path, destination: Path) -> list[str]:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    if not source.exists():
        return copied
    for child in sorted(source.iterdir(), key=lambda path: path.name):
        if child.name.startswith(".") or child.name in RUNTIME_NAMES or child.is_symlink():
            continue
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target, ignore=COPY_IGNORES)
        elif child.is_file():
            shutil.copy2(child, target)
        else:
            continue
        copied.append(child.name)
    return copied


def claude_install_commands(
    manifest: dict[str, Any],
    installed_ids: set[str],
    marketplace_names: set[str],
) -> list[list[str]]:
    commands: list[list[str]] = []
    for marketplace in manifest.get("marketplaces", []):
        name = marketplace.get("name")
        source = marketplace.get("source", {})
        if name in marketplace_names:
            continue
        source_value = source.get("repo") or source.get("url") or source.get("path")
        if source_value:
            commands.append([
                "claude", "plugin", "marketplace", "add", "--scope", "user", str(source_value)
            ])
    for plugin in manifest.get("plugins", []):
        plugin_id = plugin.get("id")
        if not plugin_id:
            continue
        if plugin_id not in installed_ids:
            commands.append([
                "claude", "plugin", "install", "--scope", plugin.get("scope", "user"),
                "--yes", plugin_id,
            ])
        if not plugin.get("enabled", True):
            commands.append(["claude", "plugin", "disable", plugin_id])
    return commands


def codex_install_commands(
    manifest: dict[str, Any],
    installed_ids: set[str],
) -> list[list[str]]:
    commands = []
    for plugin in manifest.get("plugins", []):
        plugin_id = plugin.get("id")
        if not plugin_id or plugin.get("managed") or plugin_id in installed_ids:
            continue
        commands.append(["codex", "plugin", "add", "--json", plugin_id])
    return commands


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def snapshot_plugins(
    repo: Path,
    home: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    plugins_root = repo / "plugins"
    plugins_root.mkdir(parents=True, exist_ok=True)

    claude_installed = _read_json(home / ".claude/plugins/installed_plugins.json", {"plugins": {}})
    claude_marketplaces = _read_json(home / ".claude/plugins/known_marketplaces.json", {})
    claude_settings = _read_json(home / ".claude/settings.json", {})
    claude_manifest = normalize_claude_plugins(
        claude_installed,
        claude_marketplaces,
        claude_settings.get("enabledPlugins", {}),
    )
    _write_json(plugins_root / "claude/manifest.json", claude_manifest)

    codex_manifest_path = plugins_root / "codex/manifest.json"
    try:
        result = runner(
            ["codex", "plugin", "list", "--json"],
            text=True,
            capture_output=True,
            check=True,
        )
        codex_manifest = normalize_codex_plugins(json.loads(result.stdout))
        codex_manifest = merge_codex_config_plugins(
            codex_manifest,
            (home / ".codex/config.toml").read_text(errors="replace")
            if (home / ".codex/config.toml").exists()
            else "",
        )
        _write_json(codex_manifest_path, codex_manifest)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        codex_manifest = _read_json(codex_manifest_path, {"schemaVersion": 1, "plugins": []})

    hermes = copy_local_plugins(home / ".hermes/plugins", plugins_root / "hermes/local")
    opencode = copy_local_plugins(home / ".config/opencode/plugins", plugins_root / "opencode/local")

    return {
        "claude": len(claude_manifest["plugins"]),
        "codex": len(codex_manifest.get("plugins", [])),
        "hermesLocal": hermes,
        "opencodeLocal": opencode,
    }


def load_manifest(path: Path) -> dict[str, Any]:
    return _read_json(path, {})


if __name__ == "__main__":
    raise SystemExit("Use scripts/snapshot.py or scripts/install.py instead.")
