import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/context-handoff/scripts/context_handoff.py"


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


class ContextHandoffTests(unittest.TestCase):
    def decision(self, *arguments: str) -> str:
        result = run_cli("assess", *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["decision"]

    def test_context_boundaries(self) -> None:
        self.assertEqual(
            self.decision(
                "--used-tokens", "69000", "--context-window", "100000"
            ),
            "continue",
        )
        self.assertEqual(
            self.decision(
                "--used-tokens", "70000", "--context-window", "100000"
            ),
            "checkpoint",
        )
        self.assertEqual(
            self.decision(
                "--used-tokens", "85000", "--context-window", "100000"
            ),
            "handoff-needs-authorization",
        )

    def test_compaction_authorization_and_unsafe_state(self) -> None:
        self.assertEqual(
            self.decision("--compactions", "2", "--standing-authorization"),
            "handoff-ready",
        )
        self.assertEqual(
            self.decision("--requested", "--unsafe", "test is running"),
            "handoff-deferred",
        )

    def test_packet_template_must_be_completed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            created = run_cli("template", "--output", str(packet))
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertNotEqual(run_cli("validate", str(packet)).returncode, 0)

            completed = re.sub(
                r"\[TODO:[^\]]*\]", "recorded", packet.read_text(encoding="utf-8")
            )
            packet.write_text(completed, encoding="utf-8")
            valid = run_cli("validate", str(packet))
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

    def test_probable_secret_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            run_cli("template", "--output", str(packet))
            completed = re.sub(
                r"\[TODO:[^\]]*\]", "recorded", packet.read_text(encoding="utf-8")
            )
            completed += "\nBearer " + ("a" * 30) + "\n"
            packet.write_text(completed, encoding="utf-8")
            result = run_cli("validate", str(packet))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("probable secret detected", result.stdout)


if __name__ == "__main__":
    unittest.main()
