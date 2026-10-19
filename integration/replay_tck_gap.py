"""Replay the pinned upstream test itself with controlled JSON-RPC responses.

Produces and tests a minimal patch without modifying the upstream checkout.
"""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
TCK_COMMIT = "263b9cfaf16a554bdfb166a7ba5b67716e946349"
RELATIVE = "tests/compatibility/core_operations/test_task_lifecycle.py"
OLD = '''        errors: list[str] = []
        if response.success:
            errors.append(
                "SendMessage to a terminal task should return an error, "
                "but succeeded"
            )
'''
NEW = '''        errors = validate_expected_error(response, transport, expected_error_of(req))
'''


def load_module(name, source, filename):
    module = types.ModuleType(name)
    module.__file__ = str(filename)
    sys.modules[name] = module
    exec(compile(source, str(filename), "exec"), module.__dict__)
    return module


def exercise(module, response):
    from tck.transport.jsonrpc_client import JsonRpcResponse

    completed = JsonRpcResponse(transport="jsonrpc", success=True, raw_response={
        "jsonrpc": "2.0", "id": 1, "result": {"task": {
            "id": "task-1", "contextId": "context-1", "status": {"state": "TASK_STATE_COMPLETED"},
        }},
    })
    client, collector = Mock(), Mock()
    client.transport = "jsonrpc"
    client.send_message.side_effect = [completed, response]
    client.get_task.return_value = completed
    failed = False
    try:
        module.TestMultiTurn().test_send_message_to_terminal_task(
            "jsonrpc", {"jsonrpc": client}, collector)
    except AssertionError:
        failed = True
    # A setup skip or unrelated exception propagates instead of being counted as rejection.
    collector.record.assert_called_once()
    recorded = collector.record.call_args.kwargs
    assert recorded["requirement_id"] == "CORE-SEND-002"
    assert recorded["passed"] is (not failed)
    assert client.send_message.call_count == 2
    return not failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tck_checkout", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/tck-replay")
    args = parser.parse_args()
    checkout = args.tck_checkout.resolve()
    sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if sha != TCK_COMMIT:
        raise SystemExit(f"Expected TCK {TCK_COMMIT}, got {sha}")
    if subprocess.check_output(["git", "-C", str(checkout), "diff", "HEAD", "--", "tests", "tck"], text=True):
        raise SystemExit("TCK source/test checkout has tracked modifications")
    sys.path.insert(0, str(checkout))
    from tck.transport.jsonrpc_client import JsonRpcResponse

    path = checkout / RELATIVE
    original = path.read_text()
    if original.count(OLD) != 1:
        raise SystemExit("Expected assertion block not found exactly once")
    patched = original.replace(OLD, NEW)
    before = load_module("tck_lifecycle_before", original, path)
    after = load_module("tck_lifecycle_after", patched, path)
    args.output.mkdir(parents=True, exist_ok=True)
    patch_path = ROOT / "contributions/tck-terminal-error.patch"
    patch_path.parent.mkdir(exist_ok=True)
    patch = "".join(difflib.unified_diff(
        original.splitlines(keepends=True), patched.splitlines(keepends=True),
        fromfile=f"a/{RELATIVE}", tofile=f"b/{RELATIVE}"))
    regression = ROOT / "contributions/test_terminal_message_error.py"
    patch += "".join(difflib.unified_diff(
        [], regression.read_text().splitlines(keepends=True), fromfile="/dev/null",
        tofile="b/tests/unit/test_terminal_message_error.py"))
    patch_path.write_text(patch)
    matrix = [("correct-error", -32004, True, True), ("internal-error", -32603, True, False),
              ("task-not-found", -32001, True, False), ("missing-code", None, True, False),
              ("unexpected-success", "success", False, False)]
    results = []
    for label, code, expected_before, expected_after in matrix:
        success = code == "success"
        raw = {"jsonrpc": "2.0", "id": 2}
        if success:
            raw["result"] = {"task": {"id": "task-1"}}
        else:
            raw["error"] = {"message": label}
            if code is not None:
                raw["error"]["code"] = code
        response = JsonRpcResponse(transport="jsonrpc", success=success, raw_response=raw)
        old_passed, new_passed = exercise(before, response), exercise(after, response)
        assert (old_passed, new_passed) == (expected_before, expected_after), label
        outcome = "accepted" if success else ("unsupported-operation" if code == -32004 else "other-error")
        trace = {"format": "a2a-task-trace-v1",
                 "initial": {"taskId": "task-1", "contextId": "context-1", "state": "completed"},
                 "events": [{"kind": "followup", "taskId": "task-1", "outcome": outcome}]}
        trace_path = args.output / f"{label}.json"
        trace_path.write_text(json.dumps(trace, indent=2) + "\n")
        lean = subprocess.run([str(ROOT / ".lake/build/bin/a2a-check"), str(trace_path)],
                              capture_output=True, text=True, timeout=10)
        assert lean.returncode == (0 if expected_after else 1), lean.stderr
        result = {"case": label, "upstream_passed": old_passed, "patched_passed": new_passed,
                  "lean_exit": lean.returncode}
        results.append(result)
        print(json.dumps(result))
    (args.output / "report.json").write_text(json.dumps({
        "tck_commit": sha, "scope": "actual upstream test method; synthetic JSON-RPC responses",
        "results": results,
    }, indent=2) + "\n")
    # Run the proposed upstream regression file against the patched module in memory.
    # All other test helpers and requirement objects still come from the pinned checkout.
    sys.modules["tests.compatibility.core_operations.test_task_lifecycle"] = after
    import pytest
    status = pytest.main(["-q", str(regression)])
    if status != 0:
        raise SystemExit(status)


if __name__ == "__main__":
    main()
