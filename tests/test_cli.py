"""Black-box checks of the JSON adapter, diagnostics, and semantic boundary cases.

Uses only Python's standard library. Run `lake build` first.
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / ".lake/build/bin/a2a-check"
TERMINALS = ["completed", "failed", "canceled", "rejected"]
STATES = ["unspecified", "submitted", "working", "input-required", "auth-required"] + TERMINALS


def task(state="working", task_id="t1", context="c1"):
    return {"taskId": task_id, "contextId": context, "state": state}


def snapshot(state, **kwargs):
    return {"kind": "snapshot", **task(state, **kwargs)}


def followup(outcome="accepted", **kwargs):
    return {"kind": "followup", "taskId": "t1", "outcome": outcome, **kwargs}


def trace(state="working", events=()):
    return {"format": "a2a-task-trace-v1", "initial": task(state), "events": list(events)}


class CheckerTests(unittest.TestCase):
    def run_trace(self, value, code, diagnostic=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps(value))
            result = subprocess.run([str(BINARY), str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        if diagnostic:
            self.assertIn(diagnostic, result.stdout + result.stderr)

    def test_checked_in_fixtures(self):
        expected = {
            "input-resumption.json": (0, None),
            "terminal-revival.json": (1, "events[1] TERMINAL-STABILITY"),
            "terminal-read-and-reject.json": (0, None),
            "context-mismatch.json": (1, "events[0] CONTEXT-MISMATCH"),
        }
        for filename, (code, diagnostic) in expected.items():
            with self.subTest(filename=filename):
                self.run_trace(json.loads((ROOT / "fixtures" / filename).read_text()), code, diagnostic)

    def test_all_terminal_states_are_stable(self):
        for before in TERMINALS:
            for after in STATES:
                with self.subTest(before=before, after=after):
                    self.run_trace(trace(before, [snapshot(after)]), 0 if before == after else 1)

    def test_terminal_message_outcomes(self):
        for state in TERMINALS:
            for outcome in ["accepted", "unsupported-operation", "other-error"]:
                with self.subTest(state=state, outcome=outcome):
                    self.run_trace(trace(state, [followup(outcome)]),
                                   0 if outcome == "unsupported-operation" else 1)

    def test_interrupted_resumption_and_repeated_interruptions(self):
        for state in ["input-required", "auth-required"]:
            self.run_trace(trace(state, [followup(), snapshot("working"), snapshot(state),
                                         followup(), snapshot("completed")]), 0)

    def test_nonterminal_policy_is_not_invented(self):
        for state in ["submitted", "working", "input-required", "auth-required"]:
            for outcome in ["accepted", "unsupported-operation", "other-error"]:
                self.run_trace(trace(state, [followup(outcome)]), 0)

    def test_mismatch_rejection_without_error_precedence_assumption(self):
        for state in ["working", "completed"]:
            for outcome in ["accepted", "unsupported-operation", "other-error"]:
                self.run_trace(trace(state, [followup(outcome, contextId="other")]),
                               1 if outcome == "accepted" else 0)

    def test_identity_changes_and_implicit_context(self):
        self.run_trace(trace(events=[snapshot("working", task_id="t2")]), 1, "PROFILE-TASK-IDENTITY")
        self.run_trace(trace(events=[snapshot("working", context="c2")]), 1, "CONTEXT-IDENTITY")
        self.run_trace(trace("input-required", [followup(), snapshot("working")]), 0)

    def test_first_violation_index(self):
        self.run_trace(trace(events=[snapshot("completed"), snapshot("completed"),
                                     snapshot("working"), followup()]),
                       1, "events[2] TERMINAL-STABILITY")

    def test_empty_and_incomplete_traces_are_prefixes(self):
        self.run_trace(trace(), 0)
        self.run_trace(trace(events=[snapshot("input-required")]), 0)
        self.run_trace(trace("unspecified"), 0)

    def test_invalid_inputs_do_not_become_protocol_failures(self):
        values = [None, {}, {**trace(), "format": "unknown"},
                  {**trace(), "events": "bad"}, trace(events=[{"kind": "unknown"}]),
                  trace(events=[followup(contextId=None)]),
                  trace(events=[followup(taskId="t2")]),
                  trace(events=[followup("unknown")])]
        for field, value in [("state", "unknown"), ("taskId", ""), ("contextId", "")]:
            item = copy.deepcopy(trace())
            item["initial"][field] = value
            values.append(item)
        for value in values:
            with self.subTest(value=value):
                self.run_trace(value, 2, "INPUT ERROR")

    def test_usage_missing_file_and_invalid_json(self):
        for args in [[], ["/no-such-a2a-trace.json"], ["one", "two"]]:
            result = subprocess.run([str(BINARY), *args], capture_output=True)
            self.assertEqual(result.returncode, 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{")
            self.assertEqual(subprocess.run([str(BINARY), str(path)], capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
