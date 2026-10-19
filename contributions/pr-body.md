# Description

`CORE-SEND-002` declares `UnsupportedOperationError`, but its dedicated lifecycle test currently accepts any unsuccessful response. For example, a JSON-RPC `InternalError` (`-32603`) after sending a message to a completed task is recorded as PASS, even though the required code is `-32004`.

Use the existing `validate_expected_error(response, transport, expected_error_of(req))` helper in `test_send_message_to_terminal_task`. This connects the test to its already-declared error binding, consistent with the terminal cancel test. Add five parameterized JSON-RPC regression cases that invoke the actual lifecycle test and check its recorded result:

| Follow-up response | Before | After |
| --- | --- | --- |
| UnsupportedOperationError (`-32004`) | PASS | PASS |
| InternalError (`-32603`) | PASS | FAIL |
| TaskNotFoundError (`-32001`) | PASS | FAIL |
| Error without a code | PASS | FAIL |
| Success | FAIL | FAIL |

The patch changes two test files and adds no runtime dependency.

## Validation

Validated against TCK `263b9cfaf16a554bdfb166a7ba5b67716e946349`, using the unchanged upstream lockfile and CPython 3.11.15:

- `make lint`: passed.
- `make unit-test`: 281 passed, including the five new cases.
- `git diff --check`: passed.
- Live loopback JSON-RPC run with Python SDK `01da00b0951ba6201af860d17b4c088be7902d43` and the baseline TCK-generated executor: `1 passed, 264 deselected`, zero skips, selecting `test_send_message_to_terminal_task and jsonrpc` through `run_tck.py --transport jsonrpc --level must`.

The network run covers the COMPLETED path only; it is not a full compatibility-suite result. SDK background-task/context-detach warnings were present in the server log, although the selected test passed.

## Scope and related work

This follows #150 (declared the expected error), #165 (routed this requirement to the dedicated lifecycle test), and #207 (strengthened other dedicated error assertions). None of those changes connected this particular test to the declared binding.

The shared validator retains its existing transport limitations: HTTP+JSON checks HTTP status, which can be shared by several errors. The baseline also still uses the v1.0.0 gRPC mapping; the v1.0.1 mapping update is covered separately by #232 / #240. This patch reads the registry and will follow that update without hardcoding a mapping. No new gRPC or HTTP+JSON execution coverage is claimed.

- [x] Follow the CONTRIBUTING guide.
- [x] Use a conventional commit style PR title.
- [x] Ensure tests pass within the scope described above.
- [x] Review README impact: no public API, configuration, or usage changes.

Prepared with AI assistance. No issue-closing reference is included because this patch does not resolve the broader specification-update issues.
