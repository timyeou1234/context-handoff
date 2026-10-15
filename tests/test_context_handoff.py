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
SKILL = ROOT / "skills/context-handoff/SKILL.md"


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
                "--used-tokens", "84000", "--context-window", "100000"
            ),
            "continue",
        )
        self.assertEqual(
            self.decision(
                "--used-tokens", "85000", "--context-window", "100000"
            ),
            "checkpoint",
        )
        self.assertEqual(
            self.decision(
                "--used-tokens", "95000", "--context-window", "100000", "--degradation-signals", "1"
            ),
            "handoff-needs-authorization",
        )

    def test_compaction_authorization_and_unsafe_state(self) -> None:
        self.assertEqual(
            self.decision("--compactions", "2", "--standing-authorization"),
            "checkpoint",
        )
        self.assertEqual(
            self.decision("--requested", "--unsafe", "test is running"),
            "handoff-deferred",
        )

    def test_cooldown_and_real_degradation(self):
        base = ("--compactions", "3", "--degradation-signals", "1", "--standing-authorization")
        self.assertEqual(self.decision(*base), "handoff-ready")
        self.assertEqual(self.decision(*base, "--minutes-since-handoff", "59"), "handoff-deferred")
        self.assertEqual(self.decision(*base, "--minutes-since-handoff", "60"), "handoff-ready")
        self.assertEqual(self.decision(*base, "--prior-handoff-unknown"), "handoff-deferred")
        self.assertEqual(self.decision("--compactions", "8", "--standing-authorization"), "checkpoint")
        self.assertEqual(self.decision("--used-tokens", "99000", "--context-window", "100000", "--standing-authorization"), "checkpoint")
        self.assertEqual(self.decision("--requested", "--minutes-since-handoff", "1"), "handoff-ready")
        self.assertEqual(self.decision("--degradation-signals", "2", "--standing-authorization", "--minutes-since-handoff", "1"), "handoff-ready")
        self.assertEqual(self.decision("--degradation-signals", "2", "--standing-authorization", "--unsafe", "upload"), "handoff-deferred")
        self.assertNotEqual(run_cli("assess", "--minutes-since-handoff", "nan").returncode, 0)

    def test_continuity_fields_cannot_be_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            run_cli("template", "--output", str(packet))
            completed = self.complete_packet(packet.read_text())
            for label in ("Objective", "Goal authorization", "Remaining budget", "Authorized scope and evidence", "Runtime permissions", "Chain and prior transfer", "Usage evidence"):
                packet.write_text(re.sub(rf"(?m)^- {re.escape(label)}:.*\n", "", completed))
                result = run_cli("validate", str(packet))
                self.assertNotEqual(result.returncode, 0, label)

    def test_archive_requires_goal_and_permissions_verification(self):
        result = run_cli("archive-plan", "--destination-verified", "--destination-discoverable", "--destination-opened", "--destination-thread-id", "destination-real-123", "--destination-location", "local", "--destination-host-id", "local", "--packet-available", "--source-thread-id", "real", "--source-host-id", "local", "--goal-status", "active", "--standing-preference", "--api-available", "--confirmation-available")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["archive"])
        self.assertIn("destination Goal continuity is unverified", payload["blockers"])
        self.assertIn("required destination permissions are unverified", payload["blockers"])

    def test_usage_reads_latest_cumulative_counter_without_double_counting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            def event(n):
                return {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": n, "cached_input_tokens": n // 2, "output_tokens": 10, "reasoning_output_tokens": 2, "total_tokens": n + 10}}}}
            path.write_text("\n".join(json.dumps(e) for e in [{"type": "session_meta", "payload": {"id": "exact-session"}}, event(100), event(200)]))
            result = run_cli("usage", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["totals"]["input_tokens"], 200)
            self.assertEqual(report["totals"]["uncached_input_tokens"], 100)
            self.assertIsNone(report["savings_percent"])
            self.assertNotEqual(run_cli("usage", str(path), str(path)).returncode, 0)
            copy = Path(directory) / "copy.jsonl"; copy.write_text(path.read_text())
            self.assertNotEqual(run_cli("usage", str(path), str(copy)).returncode, 0)
            with path.open("a") as f: f.write("\n" + json.dumps(event(50)))
            report = json.loads(run_cli("usage", str(path)).stdout)
            self.assertIsNone(report["totals"]["input_tokens"])
            self.assertTrue(report["sessions"][0]["counter_reset"])

    def test_usage_missing_or_partial_data_is_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            for content in ("", '{"type":"event_msg","payload":{"type":"token_count","info":null}}', '{"truncated":'):
                path.write_text(content)
                result = run_cli("usage", str(path))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsNone(json.loads(result.stdout)["totals"]["input_tokens"])

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

    def test_packet_requires_workspace_routing_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "handoff.md"
            run_cli("template", "--output", str(packet))
            completed = self.complete_packet(packet.read_text(encoding="utf-8"))
            packet.write_text(
                completed.replace("- Source workspace kind: recorded\n", ""),
                encoding="utf-8",
            )
            result = run_cli("validate", str(packet))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Workspace identity must include Source workspace kind: <value>",
                result.stdout,
            )

    def test_skill_forbids_approval_retry_across_workspace_boundary(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("HANDOFF NEEDS COMPATIBLE WORKSPACE", skill)
        self.assertIn("do not open the source-side backup packet", skill)
        self.assertIn("Do not request approval and do not retry", skill)

    def test_skill_requires_visible_openable_destination_without_pinning(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("Handoff: <short goal>", skill)
        self.assertIn("Do not pin the destination", skill)
        self.assertIn("HANDOFF VISIBILITY UNVERIFIED", skill)
        self.assertIn("task inventory", skill)
        self.assertIn("successfully open that task", skill)

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
                "Source lifecycle Goal status must be active, paused, complete, blocked, none, or unknown",
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
            "archive-plan", "--goal-continuity-verified", "--permissions-verified",
            "--destination-verified",
            "--destination-discoverable", "--destination-opened", "--destination-thread-id", "destination-real-123", "--destination-location", "local", "--destination-host-id", "local",
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
            "archive-plan", "--goal-continuity-verified", "--permissions-verified",
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
            "archive-plan", "--goal-continuity-verified", "--permissions-verified",
            "--destination-verified",
            "--destination-discoverable", "--destination-opened", "--destination-thread-id", "destination-real-123", "--destination-location", "local", "--destination-host-id", "local",
            "--goal-status",
            "active",
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
            "archive-plan", "--goal-continuity-verified", "--permissions-verified",
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
            "archive-plan", "--goal-continuity-verified", "--permissions-verified",
            "--destination-verified",
            "--destination-discoverable", "--destination-opened", "--destination-thread-id", "destination-real-123", "--destination-location", "local", "--destination-host-id", "local",
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
            "archive-plan", "--goal-continuity-verified", "--permissions-verified",
            "--destination-verified",
            "--destination-discoverable", "--destination-opened", "--destination-thread-id", "destination-real-123", "--destination-location", "local", "--destination-host-id", "local",
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

    def test_archive_plan_keeps_source_when_visibility_is_unverified(self) -> None:
        result = run_cli(
            "archive-plan", "--goal-continuity-verified", "--permissions-verified",
            "--destination-verified",
            "--packet-available",
            "--source-thread-id",
            "thread-real-123",
            "--source-host-id",
            "host-real-123",
            "--goal-status",
            "active",
            "--authorized",
            "--api-available",
            "--confirmation-available",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["archive"])
        self.assertEqual(
            payload["lifecycle_state"], "HANDOFF VISIBILITY UNVERIFIED"
        )
        self.assertTrue(payload["goal_auto_resume_risk"])

    def test_local_and_cloud_visibility_require_inventory_and_successful_open(self):
        base = ["archive-plan", "--destination-verified", "--goal-continuity-verified", "--permissions-verified", "--packet-available", "--source-thread-id", "source-real", "--source-host-id", "local", "--goal-status", "active", "--standing-preference", "--api-available", "--confirmation-available"]
        for location in ("local", "cloud"):
            with self.subTest(location=location):
                visibility = ["--destination-discoverable", "--destination-opened", "--destination-thread-id", "dest-real", "--destination-location", location]
                if location == "local":
                    visibility += ["--destination-host-id", "local"]
                ready = json.loads(run_cli(*(base + visibility)).stdout)
                self.assertTrue(ready["archive"])
                self.assertTrue(ready["visibility_verified"])
                self.assertEqual(ready["destination_location"], location)
                # Creation, a title or pin is insufficient without both read-back and open.
                for flag in ("--destination-discoverable", "--destination-opened"):
                    incomplete = [item for item in visibility if item != flag]
                    result = json.loads(run_cli(*(base + incomplete)).stdout)
                    self.assertFalse(result["archive"])
                    self.assertEqual(result["lifecycle_state"], "HANDOFF VISIBILITY UNVERIFIED")
                for flag in ("--destination-thread-id", "--destination-location") + (("--destination-host-id",) if location == "local" else ()):
                    incomplete = visibility.copy()
                    index = incomplete.index(flag)
                    del incomplete[index:index + 2]
                    result = json.loads(run_cli(*(base + incomplete)).stdout)
                    self.assertFalse(result["archive"])
                    self.assertFalse(result["visibility_verified"])

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

    def test_hook_notifies_on_severity_change_and_throttles_later_turns(self) -> None:
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
            self.assertIn("Compaction alone", first_context)

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
            self.assertEqual(json.loads(prompt.stdout), {})
            second = run_hook(compact, plugin_data)
            self.assertEqual(json.loads(second.stdout), {})
            third = run_hook(compact, plugin_data)
            third_context = json.loads(third.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("recorded 3 compaction(s)", third_context)
            for turn in range(8):
                notice = json.loads(run_hook({"session_id": "thread-sensitive-123", "hook_event_name": "UserPromptSubmit"}, plugin_data).stdout)
                self.assertEqual(bool(notice), turn == 7)

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
