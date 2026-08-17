import importlib.util
import tempfile
import unittest
from pathlib import Path


PLUGIN_SYNC_PATH = Path(__file__).resolve().parents[1] / "scripts" / "plugin_sync.py"
spec = importlib.util.spec_from_file_location("agent_air_plugin_sync", PLUGIN_SYNC_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {PLUGIN_SYNC_PATH}")
plugin_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_sync)


class NormalizeClaudePluginsTest(unittest.TestCase):
    def test_keeps_rebuild_fields_and_drops_machine_state(self) -> None:
        installed = {
            "plugins": {
                "tool@official": [{
                    "scope": "user",
                    "version": "1.2.3",
                    "gitCommitSha": "abc123",
                    "installPath": "/Users/me/.claude/plugins/cache/tool",
                    "installedAt": "today",
                    "lastUpdated": "today",
                }]
            }
        }
        marketplaces = {
            "official": {
                "source": {"source": "github", "repo": "owner/plugins"},
                "installLocation": "/Users/me/.claude/plugins/marketplaces/official",
                "lastUpdated": "today",
            }
        }
        enabled = {"tool@official": False}

        result = plugin_sync.normalize_claude_plugins(installed, marketplaces, enabled)

        self.assertEqual(result["plugins"], [{
            "id": "tool@official",
            "scope": "user",
            "version": "1.2.3",
            "gitCommitSha": "abc123",
            "enabled": False,
        }])
        self.assertEqual(result["marketplaces"], [{
            "name": "official",
            "source": {"source": "github", "repo": "owner/plugins"},
        }])
        serialized = str(result)
        self.assertNotIn("/Users/me", serialized)
        self.assertNotIn("installedAt", serialized)


class NormalizeCodexPluginsTest(unittest.TestCase):
    def test_strips_cache_paths_and_marks_runtime_plugins_managed(self) -> None:
        raw = {
            "installed": [
                {
                    "pluginId": "auth@plugins-cli",
                    "version": "5.0.0",
                    "enabled": True,
                    "marketplaceName": "plugins-cli",
                    "source": {"source": "local", "path": "/Users/me/.codex/plugins/cache/auth"},
                },
                {
                    "pluginId": "pdf@openai-primary-runtime",
                    "version": "26.1",
                    "enabled": True,
                    "marketplaceName": "openai-primary-runtime",
                    "source": {"source": "local", "path": "/Users/me/.cache/runtime/pdf"},
                },
            ]
        }

        result = plugin_sync.normalize_codex_plugins(raw)

        self.assertEqual(result["plugins"], [
            {
                "id": "auth@plugins-cli",
                "version": "5.0.0",
                "enabled": True,
                "marketplace": "plugins-cli",
                "managed": False,
            },
            {
                "id": "pdf@openai-primary-runtime",
                "version": "26.1",
                "enabled": True,
                "marketplace": "openai-primary-runtime",
                "managed": True,
            },
        ])
        self.assertNotIn("/Users/me", str(result))

    def test_merges_plugins_recorded_only_in_codex_config(self) -> None:
        manifest = {
            "schemaVersion": 1,
            "plugins": [{
                "id": "auth@plugins-cli",
                "version": "5.0.0",
                "enabled": True,
                "marketplace": "plugins-cli",
                "managed": False,
            }],
        }
        config = '''
[plugins."auth@plugins-cli"]
enabled = false

[plugins."browser@openai-bundled"]
enabled = true
'''

        result = plugin_sync.merge_codex_config_plugins(manifest, config)

        self.assertEqual(result["plugins"], [
            {
                "id": "auth@plugins-cli",
                "version": "5.0.0",
                "enabled": False,
                "marketplace": "plugins-cli",
                "managed": False,
            },
            {
                "id": "browser@openai-bundled",
                "version": "unknown",
                "enabled": True,
                "marketplace": "openai-bundled",
                "managed": True,
            },
        ])


class LocalPluginSnapshotTest(unittest.TestCase):
    def test_copies_local_plugins_but_excludes_runtime_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            (source / "my-plugin").mkdir(parents=True)
            (source / "my-plugin" / "plugin.js").write_text("export default {}")
            (source / "my-plugin" / "node_modules").mkdir()
            (source / "my-plugin" / "node_modules" / "dependency.js").write_text("large")
            (source / "cache").mkdir()
            (source / "cache" / "download.bin").write_bytes(b"cache")

            copied = plugin_sync.copy_local_plugins(source, destination)

            self.assertEqual(copied, ["my-plugin"])
            self.assertTrue((destination / "my-plugin" / "plugin.js").is_file())
            self.assertFalse((destination / "my-plugin" / "node_modules").exists())
            self.assertFalse((destination / "cache").exists())


class PluginInstallCommandTest(unittest.TestCase):
    def test_builds_only_missing_remote_plugin_commands(self) -> None:
        manifest = {
            "marketplaces": [{
                "name": "official",
                "source": {"source": "github", "repo": "owner/plugins"},
            }],
            "plugins": [
                {"id": "present@official", "scope": "user", "enabled": True},
                {"id": "missing@official", "scope": "user", "enabled": False},
            ],
        }

        commands = plugin_sync.claude_install_commands(
            manifest,
            installed_ids={"present@official"},
            marketplace_names=set(),
        )

        self.assertEqual(commands, [
            ["claude", "plugin", "marketplace", "add", "--scope", "user", "owner/plugins"],
            ["claude", "plugin", "install", "--scope", "user", "--yes", "missing@official"],
            ["claude", "plugin", "disable", "missing@official"],
        ])


if __name__ == "__main__":
    unittest.main()
