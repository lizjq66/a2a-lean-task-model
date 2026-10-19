"""Run the patched TCK test over HTTP, capture evidence, and stop our SUT."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import httpx

ROOT = Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def normalize(task):
    return {"taskId": task["id"], "contextId": task["contextId"],
            "state": task["status"]["state"].removeprefix("TASK_STATE_").lower().replace("_", "-")}


def run(checkout, output):
    output.mkdir(parents=True, exist_ok=True)
    # Confirm the candidate is actually applied (including its regression test).
    patch = ROOT / "contributions/tck-terminal-error.patch"
    subprocess.run(["git", "-C", str(checkout), "apply", "--reverse", "--check", str(patch)], check=True)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with (output / "sut.log").open("w") as log:
        server = subprocess.Popen([sys.executable, str(ROOT / "integration/network_sut.py"), str(checkout),
                                   "--port", str(port), "--traffic", str(output / "traffic.jsonl")],
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base, trust_env=False, timeout=5,
                              headers={"A2A-Version": "1.0"}) as client:
                deadline = time.monotonic() + 15
                while True:
                    check(server.poll() is None, "SUT exited; inspect sut.log")
                    try:
                        card = client.get("/.well-known/agent-card.json")
                        if card.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    check(time.monotonic() < deadline, "SUT readiness timeout")
                    time.sleep(0.1)
                (output / "agent-card.json").write_text(json.dumps(card.json(), indent=2) + "\n")
                env = {**os.environ, "UV_NO_SYNC": "1", "UV_OFFLINE": "1",
                       "NO_PROXY": "127.0.0.1,localhost"}
                command = ["uv", "run", "./run_tck.py", "--sut-host", base, "--transport", "jsonrpc",
                           "--level", "must", "-v", "--", "-k", "test_send_message_to_terminal_task and jsonrpc"]
                result = subprocess.run(command, cwd=checkout, env=env, capture_output=True, text=True, timeout=60)
                (output / "tck.log").write_text(result.stdout + result.stderr)
                print(result.stdout, end="")
                shutil.copytree(checkout / "reports", output / "reports", dirs_exist_ok=True)
                check(result.returncode == 0, "TCK failed; inspect tck.log")
                cases = ET.parse(output / "reports/junitreport.xml").findall(".//testcase")
                check(len(cases) == 1, f"Expected exactly one targeted test, got {len(cases)}")
                check(not any(c.find(tag) is not None for c in cases for tag in ("skipped", "failure", "error")),
                      "Targeted test did not pass (possibly skipped prerequisite)")

                exchanges = []
                def rpc(method, params):
                    payload = {"jsonrpc": "2.0", "id": len(exchanges) + 1, "method": method, "params": params}
                    response = client.post("/", json=payload)
                    response.raise_for_status()
                    body = response.json()
                    check(body.get("id") == payload["id"], "Response ID mismatch")
                    exchanges.append({"request": payload, "response": body})
                    return body

                created = rpc("SendMessage", {"message": {"messageId": "tck-complete-task-network-proof",
                              "role": "ROLE_USER", "parts": [{"text": "Complete for network trace"}]}})
                initial = normalize(created["result"]["task"])
                check(initial["state"] == "completed", "Task did not complete")
                task_id = initial["taskId"]
                read_before = rpc("GetTask", {"id": task_id})
                rejected = rpc("SendMessage", {"message": {"messageId": "tck-terminal-network-proof",
                               "taskId": task_id, "role": "ROLE_USER", "parts": [{"text": "Follow up"}]}})
                check(rejected.get("error", {}).get("code") == -32004, "Expected UnsupportedOperationError (-32004)")
                read_after = rpc("GetTask", {"id": task_id})
                trace = {"format": "a2a-task-trace-v1", "initial": initial, "events": [
                    {"kind": "snapshot", **normalize(read_before["result"])},
                    {"kind": "followup", "taskId": task_id, "outcome": "unsupported-operation"},
                    {"kind": "snapshot", **normalize(read_after["result"])}]}
                (output / "exchanges.json").write_text(json.dumps(exchanges, indent=2) + "\n")
                trace_path = output / "trace.json"
                trace_path.write_text(json.dumps(trace, indent=2) + "\n")
                lean = subprocess.run([str(ROOT / ".lake/build/bin/a2a-check"), str(trace_path)],
                                      capture_output=True, text=True, timeout=10)
                check(lean.returncode == 0, lean.stdout + lean.stderr)
                report = {"scope": "JSON-RPC SendMessage to completed task only", "tck_test": cases[0].attrib,
                          "tck_exit": result.returncode, "lean_exit": lean.returncode,
                          "observed_error_code": -32004, "lean_output": lean.stdout.strip(),
                          "command": command}
                (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(report, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tck_checkout", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/network")
    args = parser.parse_args()
    run(args.tck_checkout.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
