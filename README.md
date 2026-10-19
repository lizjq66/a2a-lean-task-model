# a2a-lean-task-model

A runnable research prototype that precisely defines a small part of the A2A task
lifecycle in Lean 4, proves properties of a trace checker, and provides traceable
test candidates for the A2A TCK.

The protocol baseline is **A2A v1.0.1**. This initial version covers terminal-state
stability, rejection of messages to terminal tasks, and context conflicts. It also
accepts traces that resume after an interruption. It does not define the complete
state machine or provide full A2A conformance certification.

## Running the checker

Use the Lean/Lake version specified in `lean-toolchain`. Regression tests require
Python 3 with no additional Python packages.

```sh
lake build
lake exe a2a-check fixtures/input-resumption.json
lake exe a2a-check fixtures/terminal-revival.json
python3 -m unittest discover -s tests -v
```

The first example passes. The second is expected to exit with code 1 and report:

```text
FAIL: events[1] TERMINAL-STABILITY
```

When invoking `.lake/build/bin/a2a-check FILE.json` directly, exit code 0 means the
trace satisfies the modeled subset, 1 indicates a model-rule or single-task scope
violation, and 2 indicates an input or file error. Event indices are zero-based.

## Input format

Input uses this project's **normalized trace format**, not raw A2A
JSON-RPC/REST/gRPC messages.

```json
{
  "format": "a2a-task-trace-v1",
  "initial": {"taskId": "t1", "contextId": "c1", "state": "input-required"},
  "events": [
    {"kind": "followup", "taskId": "t1", "outcome": "accepted"},
    {"kind": "snapshot", "taskId": "t1", "contextId": "c1", "state": "completed"}
  ]
}
```

- `snapshot`: a subsequent state observation for the same task, in causal order.
  Repeated snapshots of the same terminal state are allowed.
- `followup`: a completed message exchange for the task; `contextId` is optional.
  The `outcome` is `accepted`, `unsupported-operation`, or `other-error`.
- States: `unspecified`, `submitted`, `working`, `input-required`, `auth-required`,
  `completed`, `failed`, `canceled`, and `rejected`.
- Initial and subsequent snapshots require nonempty task and context IDs.
  Omitting a followup's context differs from explicit JSON `null`, which is an input error.
- Extra JSON fields are ignored. A trace must not mix tasks or include stale,
  out-of-order snapshots. Use a separate trace for followups to another task.

## Implementation and evidence

| File | Purpose |
| --- | --- |
| `A2A/Model.lean` | States, events, and declarative `Allowed` / `ValidTrace` definitions |
| `A2A/Checker.lean` | Boolean checker and diagnostics for the first violation |
| `A2A/Proofs.lean` | Proofs of soundness, completeness, terminal-state stability, and diagnostic location |
| `A2A/Json.lean` / `Main.lean` | JSON adapter and CLI, which are not formally verified |
| `fixtures/` / `tests/` | Executable positive and negative examples and boundary regression tests |

See the [rule mapping](docs/spec-mapping.md) for the full rationale, modeling
assumptions, proof boundaries, and TCK integration plan.

Six scenarios using real Python SDK handlers and TCK test-method replays with five
response variants have been completed. These identified a gap in terminal-message
error-type checking, for which a candidate patch has been prepared. See the
[integration experiments](integration/README.md) for instructions and the
[TCK audit](docs/tck-findings.md) for findings.

The modified terminal-message test has also been run over a real JSON-RPC network
connection, with network traces checked by Lean. See the
[step 2 validation record](docs/validation-step2.md). Network validation covers
rejection of followup messages to a COMPLETED task. The full official TCK has not
been run, and no changes have been submitted upstream.

The candidate patch has passed the full lint suite and 281 unit tests in a separate
TCK working copy. See the [step 1 validation record](docs/validation-step1.md).
