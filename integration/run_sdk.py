"""Exercise the real SDK request handler, then check its normalized observations.

No network transport or LLM is used; this is a deterministic handler-level probe.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
from pathlib import Path
import subprocess

from provenance import require_revision

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types.a2a_pb2 import (
    AgentCard, AgentCapabilities, AgentInterface, AgentSkill, GetTaskRequest, Message, Part,
    Role, SendMessageRequest, Task, TaskState, TaskStatus,
)
from a2a.utils.errors import A2AError, UnsupportedOperationError

ROOT = Path(__file__).resolve().parents[1]
SDK_COMMIT = "01da00b0951ba6201af860d17b4c088be7902d43"
TERMINALS = ["COMPLETED", "FAILED", "CANCELED", "REJECTED"]


class ControlledExecutor(AgentExecutor):
    def __init__(self):
        self.calls = 0

    async def execute(self, context, event_queue):
        self.calls += 1
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        if context.message.parts[0].text == "ask":
            await updater.requires_input()
        else:
            await updater.complete()

    async def cancel(self, context, event_queue):
        raise AssertionError("Cancellation is outside this probe")


def request(text, task_id="", context_id=""):
    return SendMessageRequest(message=Message(
        message_id=f"probe-{text}", role=Role.ROLE_USER,
        parts=[Part(text=text)], task_id=task_id, context_id=context_id,
    ))


def snapshot(task):
    if not isinstance(task, Task):
        raise AssertionError(f"Expected Task, got {type(task).__name__}")
    state = TaskState.Name(task.status.state).removeprefix("TASK_STATE_").lower().replace("_", "-")
    return {"taskId": task.id, "contextId": task.context_id, "state": state}


def handler(executor, store):
    card = AgentCard(
        name="Lean lifecycle probe", description="Deterministic local test executor",
        version="1", capabilities=AgentCapabilities(),
        default_input_modes=["text/plain"], default_output_modes=["text/plain"],
        supported_interfaces=[AgentInterface(url="http://localhost/unused", protocol_binding="JSONRPC", protocol_version="1.0")],
        skills=[AgentSkill(id="probe", name="Probe", description="Controlled lifecycle", tags=["test"])],
    )
    return DefaultRequestHandler(agent_executor=executor, task_store=store, agent_card=card)


async def observe_send(server, call, params):
    try:
        response = await asyncio.wait_for(server.on_message_send(params, call), 5)
        return "accepted", response, None
    except UnsupportedOperationError as error:
        return "unsupported-operation", None, type(error).__name__
    except A2AError as error:
        return "other-error", None, type(error).__name__
    # Infrastructure/programming exceptions must fail the probe, not become protocol errors.


async def terminal_case(name):
    call, executor, store = ServerCallContext(), ControlledExecutor(), InMemoryTaskStore()
    task = Task(id=f"terminal-{name.lower()}", context_id="terminal-context",
                status=TaskStatus(state=getattr(TaskState, f"TASK_STATE_{name}")))
    await store.save(task, call)
    server = handler(executor, store)
    try:
        initial = snapshot(await server.on_get_task(GetTaskRequest(id=task.id), call))
        outcome, response, error_type = await observe_send(server, call, request("resume", task.id))
        events = [{"kind": "followup", "taskId": task.id, "outcome": outcome}]
        if response is not None:
            events.append({"kind": "snapshot", **snapshot(response)})
        for _ in range(2):
            events.append({"kind": "snapshot", **snapshot(
                await server.on_get_task(GetTaskRequest(id=task.id), call))})
        return {"format": "a2a-task-trace-v1", "initial": initial, "events": events}, {
            "executor_calls": executor.calls, "error_type": error_type,
        }
    finally:
        await server.aclose()


async def resume_case(mismatch=False):
    call, executor, store = ServerCallContext(), ControlledExecutor(), InMemoryTaskStore()
    server = handler(executor, store)
    try:
        first = await asyncio.wait_for(server.on_message_send(request("ask"), call), 5)
        initial = snapshot(first)
        if initial["state"] != "input-required":
            raise AssertionError(f"Scenario setup failed: {initial}")
        supplied_context = "deliberately-wrong" if mismatch else ""
        outcome, response, error_type = await observe_send(
            server, call, request("resume", first.id, supplied_context))
        event = {"kind": "followup", "taskId": first.id, "outcome": outcome}
        if mismatch:
            event["contextId"] = supplied_context
        events = [event]
        if response is not None:
            events.append({"kind": "snapshot", **snapshot(response)})
        latest = await server.on_get_task(GetTaskRequest(id=first.id), call)
        events.append({"kind": "snapshot", **snapshot(latest)})
        expected_state = "input-required" if mismatch else "completed"
        if snapshot(latest)["state"] != expected_state:
            raise AssertionError("Controlled executor's expected result was not observed")
        return {"format": "a2a-task-trace-v1", "initial": initial, "events": events}, {
            "executor_calls": executor.calls, "error_type": error_type,
        }
    finally:
        await server.aclose()


async def run(output):
    output.mkdir(parents=True, exist_ok=True)
    # Keep SDK-created tasks alive until explicitly drained. This standalone loop is ours.
    retained = set()
    def retain(loop, coro, **kwargs):
        task = asyncio.Task(coro, loop=loop, **kwargs)
        retained.add(task)
        task.add_done_callback(retained.discard)
        return task
    asyncio.get_running_loop().set_task_factory(retain)
    results = []
    cases = [(f"terminal-{name.lower()}", terminal_case, name) for name in TERMINALS]
    cases += [("input-resumption", resume_case, False), ("context-mismatch", resume_case, True)]
    for name, scenario, arg in cases:
        try:
            trace, details = await scenario(arg)
        finally:
            pending = [t for t in retained if not t.done()]
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        details["background_tasks_drained_after_handler_close"] = len(pending)
        path = output / f"{name}.json"
        path.write_text(json.dumps(trace, indent=2) + "\n")
        checked = subprocess.run([str(ROOT / ".lake/build/bin/a2a-check"), str(path)],
                                 text=True, capture_output=True, timeout=10)
        result = {"case": name, **details, "checker_exit": checked.returncode,
                  "checker_output": checked.stdout.strip()}
        results.append(result)
        print(json.dumps(result))
    report = {"sdk_commit": SDK_COMMIT, "sdk_version": importlib.metadata.version("a2a-sdk"),
              "scope": "in-process DefaultRequestHandlerV2; no wire transport", "results": results}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if any(r["checker_exit"] != 0 for r in results):
        raise AssertionError("SDK observation violated the modeled fragment; see report")
    for result in results:
        expected_calls = 2 if result["case"] == "input-resumption" else (1 if result["case"] == "context-mismatch" else 0)
        if result["executor_calls"] != expected_calls:
            raise AssertionError(f"Unexpected executor invocation: {result}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/sdk")
    args = parser.parse_args()
    require_revision("a2a-sdk", SDK_COMMIT)
    asyncio.run(run(args.output))


if __name__ == "__main__":
    main()
