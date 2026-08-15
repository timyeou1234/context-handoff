import json
import os
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
HOOKS_CONFIG = ROOT / "hooks/hooks.json"
HOOK_SCRIPT = ROOT / "hooks/context_health.py"


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def run_hook(
    payload: dict[str, object], plugin_data: Path
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PLUGIN_DATA"] = str(plugin_data)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


class ContextHandoffTests(unittest.TestCase):
    @staticmethod
    def complete_packet(
        text: str,
        *,
        reply_language: str = "Traditional Chinese (zh-Hant)",
        locale: str = "Asia/Taipei",
    ) -> str:
        text = re.sub(
            r"- Reply language: \[TODO:[^\]]*\]",
            f"- Reply language: {reply_language}",
            text,
        )
        text = re.sub(
            r"- Locale or time zone: \[TODO:[^\]]*\]",
            f"- Locale or time zone: {locale}",
            text,
        )
        return re.sub(r"\[TODO:[^\]]*\]", "recorded", text)

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

            completed = self.complete_packet(packet.read_text(encoding="utf-8"))
            packet.write_text(completed, encoding="utf-8")
            valid = run_cli("validate", str(packet))
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

    def test_packet_requires_communication_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            run_cli("template", "--output", str(packet))
            completed = self.complete_packet(packet.read_text(encoding="utf-8"))
            without_preferences = re.sub(
                r"(?ms)^## Communication preferences\n.*?(?=^## )",
                "",
                completed,
            )
            packet.write_text(without_preferences, encoding="utf-8")
            result = run_cli("validate", str(packet))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "missing or empty section: Communication preferences",
                result.stdout,
            )

            packet.write_text(
                completed.replace(
                    "- Reply language: Traditional Chinese (zh-Hant)\n", ""
                ),
                encoding="utf-8",
            )
            missing_language = run_cli("validate", str(packet))
            self.assertNotEqual(missing_language.returncode, 0)
            self.assertIn(
                "Communication preferences must include Reply language: <value>",
                missing_language.stdout,
            )

    def test_packet_preserves_reply_language_and_locale_separately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            run_cli("template", "--output", str(packet))
            completed = self.complete_packet(
                packet.read_text(encoding="utf-8"),
                reply_language="Traditional Chinese (zh-Hant)",
                locale="unspecified",
            )
            packet.write_text(completed, encoding="utf-8")
            result = run_cli("validate", str(packet))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(
                "- Reply language: Traditional Chinese (zh-Hant)", completed
            )
            self.assertIn("- Locale or time zone: unspecified", completed)

    def test_probable_secret_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            run_cli("template", "--output", str(packet))
            completed = self.complete_packet(packet.read_text(encoding="utf-8"))
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
        self.assertRegex(
            manifest["version"], r"^\d+\.\d+\.\d+(?:\+[0-9A-Za-z.-]+)?$"
        )
        self.assertEqual(manifest["skills"], "./skills/")
        base_version = manifest["version"].split("+", 1)[0]
        self.assertGreaterEqual(tuple(map(int, base_version.split("."))), (0, 3, 0))
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

    def test_plugin_bundles_compaction_lifecycle_hooks(self) -> None:
        hooks = json.loads(HOOKS_CONFIG.read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(hooks["SessionStart"][0]["matcher"], "^compact$")
        for event in ("SessionStart", "UserPromptSubmit", "SessionEnd"):
            command = hooks[event][0]["hooks"][0]["command"]
            self.assertIn("$PLUGIN_ROOT/hooks/context_health.py", command)
        self.assertNotIn("Stop", hooks)

    def test_hook_records_compactions_and_reminds_each_later_turn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_data = Path(directory)
            compact = {
                "session_id": "thread-sensitive-123",
                "cwd": "/tmp/example",
                "hook_event_name": "SessionStart",
                "source": "compact",
            }

            first = run_hook(compact, plugin_data)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_output = json.loads(first.stdout)
            first_context = first_output["hookSpecificOutput"]["additionalContext"]
            self.assertIn("recorded 1 compaction(s)", first_context)
            self.assertIn("create or refresh a checkpoint", first_context)

            prompt = run_hook(
                {
                    "session_id": "thread-sensitive-123",
                    "cwd": "/tmp/example",
                    "hook_event_name": "UserPromptSubmit",
                    "turn_id": "turn-2",
                    "prompt": "continue",
                },
                plugin_data,
            )
            prompt_context = json.loads(prompt.stdout)["hookSpecificOutput"][
                "additionalContext"
            ]
            self.assertIn("At the start of this user turn", prompt_context)
            self.assertIn("recorded 1 compaction(s)", prompt_context)

            second = run_hook(compact, plugin_data)
            second_context = json.loads(second.stdout)["hookSpecificOutput"][
                "additionalContext"
            ]
            self.assertIn("recorded 2 compaction(s)", second_context)
            self.assertIn("treat this as handoff-ready", second_context)

            state_files = list((plugin_data / "context-health").glob("*.json"))
            self.assertEqual(len(state_files), 1)
            self.assertNotIn("thread-sensitive-123", state_files[0].name)
            self.assertNotIn(
                "thread-sensitive-123", state_files[0].read_text(encoding="utf-8")
            )

    def test_hook_keeps_sessions_separate_and_cleans_up_on_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_data = Path(directory)
            base = {
                "cwd": "/tmp/example",
                "hook_event_name": "SessionStart",
                "source": "compact",
            }
            run_hook({**base, "session_id": "session-a"}, plugin_data)
            run_hook({**base, "session_id": "session-b"}, plugin_data)
            self.assertEqual(
                len(list((plugin_data / "context-health").glob("*.json"))), 2
            )

            ended = run_hook(
                {
                    "session_id": "session-a",
                    "cwd": "/tmp/example",
                    "hook_event_name": "SessionEnd",
                    "reason": "other",
                },
                plugin_data,
            )
            self.assertEqual(ended.returncode, 0, ended.stderr)
            self.assertEqual(json.loads(ended.stdout), {})
            self.assertEqual(
                len(list((plugin_data / "context-health").glob("*.json"))), 1
            )

            no_history = run_hook(
                {
                    "session_id": "session-never-compacted",
                    "cwd": "/tmp/example",
                    "hook_event_name": "UserPromptSubmit",
                    "turn_id": "turn-1",
                    "prompt": "hello",
                },
                plugin_data,
            )
            self.assertEqual(json.loads(no_history.stdout), {})


if __name__ == "__main__":
    unittest.main()
