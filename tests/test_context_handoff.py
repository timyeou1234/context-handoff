import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/context-handoff/scripts/context_handoff.py"
MANIFEST = ROOT / ".codex-plugin/plugin.json"
MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"


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

    def test_archive_plan_allows_verified_authorized_recoverable_handoff(self) -> None:
        result = run_cli(
            "archive-plan",
            "--destination-verified",
            "--packet-available",
            "--source-thread-id", "thread-real-123",
            "--source-host-id", "host-real-456",
            "--authorized",
            "--api-available",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "archive-ready")
        self.assertTrue(payload["archive"])

    def test_archive_plan_rejects_unverified_or_unsafe_handoff(self) -> None:
        result = run_cli(
            "archive-plan",
            "--packet-available",
            "--source-thread-id", "thread-real-123",
            "--source-host-id", "host-real-456",
            "--authorized",
            "--api-available",
            "--unsafe", "test is running",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "archive-skipped")
        self.assertIn("destination has not reported HANDOFF VERIFIED", payload["blockers"])
        self.assertIn("unsafe state: test is running", payload["blockers"])

    def test_archive_plan_requires_real_ids_authorization_packet_and_api(self) -> None:
        result = run_cli("archive-plan", "--destination-verified")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["archive"])
        self.assertIn("validated recovery packet is unavailable", payload["blockers"])
        self.assertIn(
            "surface-provided source thread and host identifiers are required",
            payload["blockers"],
        )
        self.assertIn("source archival is not authorized", payload["blockers"])
        self.assertIn(
            "thread archival API is unavailable; use manual archive fallback",
            payload["blockers"],
        )

    def test_plugin_manifest_and_assets_are_consistent(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "context-handoff")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertNotIn("apps", manifest)
        self.assertNotIn("mcpServers", manifest)
        for key in ("composerIcon", "logo"):
            asset = ROOT / manifest["interface"][key]
            self.assertTrue(asset.is_file(), f"missing {key}: {asset}")
        self.assertLessEqual(len(manifest["interface"]["defaultPrompt"]), 3)
        self.assertTrue(
            all(len(prompt) <= 128 for prompt in manifest["interface"]["defaultPrompt"])
        )

    def test_repo_marketplace_resolves_plugin_root(self) -> None:
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "context-handoff")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        plugin_root = (ROOT / entry["source"]["path"]).resolve()
        self.assertEqual(plugin_root, ROOT.resolve())
        self.assertTrue((plugin_root / ".codex-plugin/plugin.json").is_file())


if __name__ == "__main__":
    unittest.main()
