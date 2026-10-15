import importlib.util
import json
import tempfile
import unittest
import subprocess
import sys
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

    def compaction_events(self):
        # Sanitized real 0.3.6 native trace: compaction was absent from legacy totals.
        def ledger(stamp, inp, cache, output, reasoning):
            return {"timestamp":stamp,"type":"token_usage_record","payload":{
                "thread_id":"exact", "usage":{"total_tokens":999999},
                "thread_token_usage":{"input_tokens":inp,"cached_input_tokens":cache,
                    "cache_write_input_tokens":0,"output_tokens":output,
                    "reasoning_output_tokens":reasoning,"total_tokens":inp+output}}}
        rows = [self.events()[0], ledger("2026-01-01T00:00:01Z",17999,0,19,0),
            {"timestamp":"2026-01-01T00:00:02Z","type":"compacted","payload":{}},
            ledger("2026-01-01T00:00:03Z",36037,17792,264,0),
            ledger("2026-01-01T00:00:04Z",140372,120064,1050,43)]
        old=self.events()[4];old["timestamp"]="2026-01-01T00:00:05Z"
        old["payload"]["info"]["total_token_usage"].update(input_tokens=122334,
            cached_input_tokens=102272,output_tokens=805,reasoning_output_tokens=43,total_tokens=123139)
        return rows+[old, rows[-1].copy()]

    def test_compaction_included_once_by_both_commands(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.write(t,self.compaction_events());end=evidence.snapshot(p,"exact")
            self.assertEqual(end["usage"]["total_tokens"],141422)
            self.assertEqual(end["usage_advances"],3)
            start=evidence.snapshot(p,"exact","2026-01-01T00:00:01Z")
            compact=evidence.snapshot(p,"exact","2026-01-01T00:00:03Z")
            self.assertEqual(evidence.interval(start,compact)["usage"]["total_tokens"],18283)
            cli=subprocess.run([sys.executable,str(SCRIPT.with_name("context_handoff.py")),"usage",str(p)],capture_output=True,text=True)
            self.assertEqual(cli.returncode,0,cli.stderr)
            self.assertEqual(json.loads(cli.stdout)["totals"],end["usage"])

    def test_ledger_identity_reset_and_invalid_counters_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            for update in [{"input_tokens":1},{"cached_input_tokens":True},
                           {"total_tokens":-1},{"reasoning_output_tokens":99999}]:
                rows=self.compaction_events();rows[-1]=json.loads(json.dumps(rows[-1]))
                rows[-1]["payload"]["thread_token_usage"].update(update)
                with self.assertRaises(ValueError):evidence.snapshot(self.write(t,rows),"exact")
            rows=self.compaction_events();rows[1]["payload"]["thread_id"]="other"
            with self.assertRaises(ValueError):evidence.snapshot(self.write(t,rows),"exact")
            rows=self.compaction_events();rows[1]["payload"].pop("thread_token_usage")
            with self.assertRaises(ValueError):evidence.snapshot(self.write(t,rows),"exact")

    def test_no_mixed_bases_or_legacy_compaction_claim(self):
        with tempfile.TemporaryDirectory() as t:
            legacy=evidence.snapshot(self.write(t,self.events()),"exact")
            modern=evidence.snapshot(self.write(t,self.compaction_events()),"exact")
            with self.assertRaises(ValueError):evidence.interval(legacy,modern)
            with self.assertRaises(ValueError):evidence.interval(modern,dict(modern,cutoff="2025"))
            rows=self.events()+[{"type":"compacted","payload":{}}]
            with self.assertRaisesRegex(ValueError,"compaction accounting unavailable"):
                evidence.snapshot(self.write(t,rows),"exact")

    def test_ledger_missing_optional_fields_remain_unknown_and_stale_fails(self):
        with tempfile.TemporaryDirectory() as t:
            rows=self.compaction_events()[:4]
            rows[-1]["payload"]["thread_token_usage"].pop("cached_input_tokens")
            r=evidence.snapshot(self.write(t,rows),"exact")
            self.assertIsNone(r["usage"]["cached_input_tokens"])
            self.assertIsNone(r["usage"]["uncached_input_tokens"])
            rows=self.compaction_events();old=rows[-2]["payload"]["info"]["total_token_usage"]
            old.update(input_tokens=200000,total_tokens=200805)
            with self.assertRaisesRegex(ValueError,"incomplete telemetry"):
                evidence.snapshot(self.write(t,rows),"exact")

if __name__ == "__main__": unittest.main()
