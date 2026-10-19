# SDK and TCK integration experiments

These two independent experiments connect the Lean model to real implementations.
No LLM, credentials, or external agent is required.

## Setup

```sh
lake build
uv venv .venv
uv pip install --python .venv/bin/python -r integration/requirements.txt
```

`requirements.txt` pins the Python runtime dependencies and SDK/TCK source commits
used for this run. Installation may require network access and build dependencies;
this is not a hash-verified build lockfile covering all platforms. You can also
install the SDK/TCK from clean local checkouts of the same commits.

## Real SDK handler experiment

```sh
.venv/bin/python integration/run_sdk.py
```

The experiment uses the real `DefaultRequestHandlerV2`, `InMemoryTaskStore`, and
`TaskUpdater` with a deterministic executor. Six scenarios generate normalized
traces and invoke the Lean binary:

- Seed each of the four terminal states in the store, then send a followup and
  query repeatedly. Verify rejection and that the executor did not run.
- Create an input-required task, resume it with a followup that omits context,
  and complete it. Check that the task and context remain unchanged.
- Supply an incorrect context for an input-required task. Check rejection and
  that the executor did not run again.

Output is written to `artifacts/sdk/`, including six traces and `report.json`.
The script verifies the installed source commits. Infrastructure errors and
timeouts fail the experiment; they are not mapped to protocol-permitted
“other errors.”

Scope: this is **in-process handler integration**, not HTTP/gRPC/JSON-RPC
end-to-end validation. The four terminal states are seeded in the store, so their
creation paths are not tested. Authentication resumption is not tested.

In the seeded-terminal-state experiment, the current SDK leaves two background
tasks pending after `handler.aclose()`. The experiment retains task references in
its own event loop and explicitly cancels and awaits them, recording the count in
the report. This observation is separate from the lifecycle protocol assertions;
its cause has not been diagnosed, and it is not treated as a confirmed SDK bug.

## TCK gap replay and candidate patch

A pinned TCK checkout is required to execute the upstream test file itself:

```sh
git clone https://github.com/a2aproject/a2a-tck.git /tmp/a2a-tck-lean-integration
git -C /tmp/a2a-tck-lean-integration checkout 263b9cfaf16a554bdfb166a7ba5b67716e946349
.venv/bin/python integration/replay_tck_gap.py /tmp/a2a-tck-lean-integration
git -C /tmp/a2a-tck-lean-integration apply --check "$PWD/contributions/tck-terminal-error.patch"
```

The script executes the original `TestMultiTurn.test_send_message_to_terminal_task`
and a version with only its assertions changed, using the real TCK
`JsonRpcResponse` and requirements registry with controlled responses injected.
It verifies the compatibility collector's results to ensure prerequisite skips are
not counted as passes. The same responses are normalized and passed to the Lean
checker to cross-check the verdicts.

The script also runs five candidate upstream regression tests against the patched
version in memory. It generates `contributions/tck-terminal-error.patch`, containing
the assertion fix and regression tests, along with `artifacts/tck-replay/`.
It does not modify the upstream checkout or publish a PR.

| Injected JSON-RPC result | Original test | Candidate patch | Lean |
| --- | --- | --- | --- |
| UnsupportedOperationError / -32004 | Pass | Pass | Pass |
| InternalError / -32603 | **False pass** | Reject | Reject |
| TaskNotFoundError / -32001 | **False pass** | Reject | Reject |
| Error response without a code | **False pass** | Reject | Reject |
| Success response | Reject | Reject | Reject |

This is a **synthetic response replay** of the test assertions, not evidence that
the real SDK returned an incorrect error type. The shared validator's precision
on other transports depends on the TCK's existing bindings; only JSON-RPC was
replayed here. In particular, distinct semantic errors may share HTTP status
codes, so this experiment does not establish strict error-type discrimination
across all transports.

The candidate patch has passed the full lint suite and 281 unit tests in a separate
TCK working copy. See the [step 1 validation record](../docs/validation-step1.md)
for the environment, patch hash, and issues addressed.

## Real JSON-RPC network experiment

Prepare a separate TCK checkout with the candidate patch applied and install its
development environment using its `uv.lock`, then run:

```sh
.venv/bin/python integration/run_network.py /private/tmp/a2a-tck-validation-20261018
```

Permission to bind a local loopback port is required. The script starts the SDK
service using the Python environment with this project's integration dependencies
installed, then runs the official runner in the TCK's own environment. It selects
only the JSON-RPC terminal-message test. The server reuses the upstream generative
executor without changing its business logic. Results are written to
`artifacts/network/`, and the script shuts down the service it started after either
success or failure.

The script also runs an additional sequence: complete a task, query it, reject a
followup message, and query it again. It normalizes the actual responses and passes
them to Lean. Successful validation and known log observations are documented in
the [step 2 validation record](../docs/validation-step2.md).
