import importlib.util
import tempfile
import unittest
from pathlib import Path


SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "snapshot.py"
spec = importlib.util.spec_from_file_location("agent_air_snapshot", SNAPSHOT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {SNAPSHOT_PATH}")
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


def write_skill(root: Path, agent: str, folder: str, declared_name: str, body: str) -> Path:
    skill_dir = root / agent / folder
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {declared_name}\ndescription: test\n---\n\n{body}\n"
    )
    return skill_dir


class ConsolidateDuplicateSkillsTest(unittest.TestCase):
    def test_promotes_identical_agent_copies_to_shared(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "skills"
            write_skill(root, "claude", "tool-a", "tool-a", "same")
            write_skill(root, "codex", "different-folder", "tool-a", "same")

            promoted = snapshot.consolidate_duplicate_skills(root)

            self.assertEqual(promoted, ["tool-a"])
            self.assertTrue((root / "shared" / "tool-a" / "SKILL.md").is_file())
            self.assertFalse((root / "claude" / "tool-a").exists())
            self.assertFalse((root / "codex" / "different-folder").exists())

    def test_does_not_merge_same_name_when_contents_differ(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "skills"
            write_skill(root, "claude", "tool-a", "tool-a", "claude variant")
            write_skill(root, "codex", "tool-a", "tool-a", "codex variant")

            promoted = snapshot.consolidate_duplicate_skills(root)

            self.assertEqual(promoted, [])
            self.assertFalse((root / "shared" / "tool-a").exists())
            self.assertTrue((root / "claude" / "tool-a" / "SKILL.md").is_file())
            self.assertTrue((root / "codex" / "tool-a" / "SKILL.md").is_file())

    def test_existing_shared_copy_wins_over_agent_variant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "skills"
            write_skill(root, "shared", "tool-a", "tool-a", "canonical")
            write_skill(root, "claude", "tool-a", "tool-a", "variant")

            promoted = snapshot.consolidate_duplicate_skills(root)

            self.assertEqual(promoted, [])
            self.assertTrue((root / "shared" / "tool-a" / "SKILL.md").is_file())
            self.assertFalse((root / "claude" / "tool-a").exists())


if __name__ == "__main__":
    unittest.main()
