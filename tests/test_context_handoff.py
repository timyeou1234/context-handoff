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
        text = re.sub(
            r"- Goal status: \[TODO:[^\]]*\]",
            "- Goal status: active",
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

    def test_packet_requires_explicit_source_goal_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            run_cli("template", "--output", str(packet))
            completed = self.complete_packet(packet.read_text(encoding="utf-8"))
            packet.write_text(
                completed.replace("- Goal status: active", "- Goal status: running"),
                encoding="utf-8",
            )
            result = run_cli("validate", str(packet))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Source lifecycle Goal status must be active, complete, blocked, none, or unknown",
                result.stdout,
            )

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
            "--goal-status", "active",
            "--authorized",
            "--api-available",
            "--confirmation-available",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "archive-ready")
        self.assertTrue(payload["archive"])
        self.assertEqual(payload["lifecycle_state"], "SOURCE_ARCHIVE_READY")
        self.assertTrue(payload["goal_auto_resume_risk"])

    def test_archive_plan_rejects_unverified_or_unsafe_handoff(self) -> None:
        result = run_cli(
            "archive-plan",
            "--packet-available",
            "--source-thread-id", "thread-real-123",
            "--source-host-id", "host-real-456",
            "--goal-status", "active",
            "--authorized",
            "--api-available",
            "--confirmation-available",
            "--unsafe", "test is running",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "archive-skipped")
        self.assertIn("destination has not reported HANDOFF VERIFIED", payload["blockers"])
        self.assertIn("unsafe state: test is running", payload["blockers"])
        self.assertEqual(payload["lifecycle_state"], "CHECKPOINTED")

    def test_archive_plan_requires_real_ids_authorization_packet_and_api(self) -> None:
        result = run_cli(
            "archive-plan", "--destination-verified", "--goal-status", "active"
        )
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
        self.assertIn(
            "source archival cannot be confirmed on this surface",
            payload["blockers"],
        )
        self.assertEqual(
            payload["decision"], "handoff-verified-source-still-active"
        )
        self.assertTrue(payload["manual_fallback_required"])

    def test_archive_plan_never_closes_on_destination_regression(self) -> None:
        result = run_cli(
            "archive-plan",
            "--destination-regression",
            "--packet-available",
            "--source-thread-id", "thread-real-123",
            "--source-host-id", "host-real-456",
            "--goal-status", "active",
            "--authorized",
            "--api-available",
            "--confirmation-available",
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["archive"])
        self.assertEqual(payload["lifecycle_state"], "CHECKPOINTED")
        self.assertIn("destination reported HANDOFF REGRESSION", payload["blockers"])

    def test_archive_plan_treats_observed_archive_as_idempotent_success(self) -> None:
        result = run_cli(
            "archive-plan",
            "--destination-verified",
            "--packet-available",
            "--source-thread-id", "thread-real-123",
            "--source-host-id", "host-real-456",
            "--goal-status", "active",
            "--already-archived",
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["archive"])
        self.assertTrue(payload["archived_confirmed"])
        self.assertEqual(payload["decision"], "archive-confirmed")
        self.assertEqual(payload["lifecycle_state"], "SOURCE_ARCHIVED_CONFIRMED")

    def test_archive_plan_accepts_documented_standing_preference(self) -> None:
        result = run_cli(
            "archive-plan",
            "--destination-verified",
            "--packet-available",
            "--source-thread-id", "thread-real-123",
            "--source-host-id", "host-real-456",
            "--goal-status", "unknown",
            "--standing-preference",
            "--api-available",
            "--confirmation-available",
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["archive"])
        self.assertEqual(payload["decision"], "archive-ready")
        self.assertTrue(payload["goal_auto_resume_risk"])

    def test_archive_result_requires_observed_confirmation(self) -> None:
        confirmed = run_cli(
            "archive-result",
            "--destination-verified",
            "--goal-status", "active",
            "--archive-confirmed",
        )
        confirmed_payload = json.loads(confirmed.stdout)
        self.assertTrue(confirmed_payload["archived_confirmed"])
        self.assertEqual(
            confirmed_payload["lifecycle_state"], "SOURCE_ARCHIVED_CONFIRMED"
        )
        self.assertFalse(confirmed_payload["source_auto_resume_risk"])

        failed = run_cli(
            "archive-result",
            "--destination-verified",
            "--goal-status", "active",
            "--failure", "archive API returned an error",
        )
        failed_payload = json.loads(failed.stdout)
        self.assertFalse(failed_payload["archived_confirmed"])
        self.assertEqual(
            failed_payload["lifecycle_state"],
            "HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE",
        )
        self.assertTrue(failed_payload["source_auto_resume_risk"])
        self.assertEqual(failed_payload["failure"], "archive API returned an error")

    def test_archive_result_never_claims_closure_on_regression(self) -> None:
        result = run_cli(
            "archive-result",
            "--destination-regression",
            "--goal-status", "active",
            "--archive-confirmed",
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["archived_confirmed"])
        self.assertEqual(payload["decision"], "archive-prohibited")
        self.assertEqual(payload["lifecycle_state"], "CHECKPOINTED")

    def test_plugin_manifest_and_assets_are_consistent(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "context-handoff")
        self.assertRegex(
            manifest["version"], r"^\d+\.\d+\.\d+(?:\+[0-9A-Za-z.-]+)?$"
        )
        self.assertEqual(manifest["skills"], "./skills/")
        base_version = manifest["version"].split("+", 1)[0]
        self.assertGreaterEqual(tuple(map(int, base_version.split("."))), (0, 3, 2))
        self.assertNotIn("apps", manifest)
        self.assertNotIn("mcpServers", manifest)
        for key in ("composerIcon", "logo"):
            asset = ROOT / manifest["interface"][key]
            self.assertTrue(asset.is_file(), f"missing {key}: {asset}")
            png = asset.read_bytes()
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            width = int.from_bytes(png[16:20], "big")
            height = int.from_bytes(png[20:24], "big")
            minimum = 48 if key == "composerIcon" else 256
            self.assertEqual(width, height, f"{key} must be square")
            self.assertGreaterEqual(width, minimum, f"{key} is too small")
        self.assertLessEqual(len(manifest["interface"]["defaultPrompt"]), 3)
        self.assertLessEqual(len(manifest["interface"]["shortDescription"]), 30)
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
