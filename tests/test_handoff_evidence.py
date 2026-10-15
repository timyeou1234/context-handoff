import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/context-handoff/scripts/handoff_evidence.py"
spec = importlib.util.spec_from_file_location("evidence", SCRIPT)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)

class EvidenceTests(unittest.TestCase):
    def events(self, kind="custom_tool_call"):
        output_kind = kind + "_output"
        return [
            {"type":"session_meta","payload":{"id":"exact"}},
            {"timestamp":"2026-01-01T00:00:00Z","type":"turn_context","payload":{"model":"test","effort":"high"}},
            {"timestamp":"2026-01-01T00:00:01Z","type":"response_item","payload":{"type":kind,"name":"exec","call_id":"call1","input":"text(await tools.get_goal({}))"}},
            {"timestamp":"2026-01-01T00:00:02Z","type":"response_item","payload":{"type":output_kind,"call_id":"call1","output":[{"type":"input_text","text":json.dumps({"value":{"goal":None,"remainingTokens":None,"completionBudgetReport":None}})}]}},
            {"timestamp":"2026-01-01T00:00:03Z","type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":100,"cached_input_tokens":80,"output_tokens":10,"reasoning_output_tokens":2,"total_tokens":110}}}},
            {"timestamp":"2026-01-01T00:00:04Z","type":"event_msg","payload":{"type":"task_complete"}},
        ]

    def write(self, directory, events):
        p=Path(directory)/"rollout-exact.jsonl"
        p.write_text("".join(json.dumps(e)+"\n" for e in events))
        return p

    def test_both_tool_formats_and_actual_goal(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in ["custom_tool_call","function_call"]:
                r=evidence.snapshot(self.write(t,self.events(kind)),"exact")
                self.assertEqual(r["goal_evidence"]["goal"],None)
                self.assertEqual(r["usage"]["uncached_input_tokens"],20)
                self.assertIsNone(r["usage"]["cache_write_input_tokens"])
                self.assertEqual(r["task_complete_at"],"2026-01-01T00:00:04Z")

    def test_unrelated_or_spoofed_text_is_not_goal_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            events=self.events();events[3]["payload"]["call_id"]="unrelated"
            self.assertIsNone(evidence.snapshot(self.write(t,events),"exact")["goal_evidence"])
            events=self.events();events[3]["payload"]["output"]='a quoted assertion: "goal": null'
            self.assertIsNone(evidence.snapshot(self.write(t,events),"exact")["goal_evidence"])

    def test_exact_archive_relocation_and_identity(self):
        with tempfile.TemporaryDirectory() as t:
            original=Path(t)/"sessions/2026/01/01/rollout-exact.jsonl"
            archive=Path(t)/"archived_sessions";archive.mkdir()
            self.write(archive,self.events())
            self.assertEqual(evidence.snapshot(original,"exact")["session_id"],"exact")
            with self.assertRaises(ValueError): evidence.snapshot(original,"wrong")
            with self.assertRaises(OSError): evidence.snapshot(original.with_name("other.jsonl"),"exact")

    def test_cumulative_duplicates_cutoff_and_delta(self):
        with tempfile.TemporaryDirectory() as t:
            events=self.events();events.append(events[4].copy())
            later=json.loads(json.dumps(events[4]));later["timestamp"]="2026-01-01T00:00:05Z"
            later["payload"]["info"]["total_token_usage"].update(input_tokens=150,cached_input_tokens=120,total_tokens=160)
            events.append(later);p=self.write(t,events)
            start=evidence.snapshot(p,"exact","2026-01-01T00:00:03Z")
            end=evidence.snapshot(p,"exact")
            self.assertEqual(end["usage_advances"],2)
            self.assertEqual(evidence.interval(start,end)["usage"]["total_tokens"],50)
            self.assertEqual(start["usage"]["total_tokens"],110)

    def test_reset_bad_counters_and_truncation_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            for update in [{"input_tokens":90,"total_tokens":100},{"cached_input_tokens":101},{"reasoning_output_tokens":11},{"input_tokens":True},{"total_tokens":999}]:
                events=self.events();later=json.loads(json.dumps(events[4]));later["payload"]["info"]["total_token_usage"].update(update);events.append(later)
                with self.assertRaises(ValueError): evidence.snapshot(self.write(t,events),"exact")
            events=self.events()
            missing=json.loads(json.dumps(events[4]));missing["payload"]["info"]["total_token_usage"].pop("cached_input_tokens")
            reset=json.loads(json.dumps(events[4]));reset["payload"]["info"]["total_token_usage"]["cached_input_tokens"]=70
            events.extend([missing,reset])
            with self.assertRaises(ValueError): evidence.snapshot(self.write(t,events),"exact")
            p=self.write(t,self.events());p.write_text(p.read_text()+'{')
            with self.assertRaises(ValueError): evidence.snapshot(p,"exact")

    def test_interval_identity_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as t:
            r=evidence.snapshot(self.write(t,self.events()),"exact")
            self.assertIsNone(evidence.interval(r,r)["usage"]["cache_write_input_tokens"])
            other=dict(r,session_id="other")
            with self.assertRaises(ValueError): evidence.interval(r,other)

if __name__ == "__main__": unittest.main()
