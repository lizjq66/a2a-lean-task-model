# TCK 审计与实验结果（2026-10-18）

本次直接读取固定 checkout，并运行真实 SDK handler 与 TCK 测试方法回放。

| 组件 | Commit |
| --- | --- |
| A2A 规范 v1.0.1 | `3303592588e388e62e0f69f701af531d2f4e3991` |
| TCK | `263b9cfaf16a554bdfb166a7ba5b67716e946349` |
| Python SDK | `01da00b0951ba6201af860d17b4c088be7902d43` |

## 已复现的最小缺口

`CORE-SEND-002` 的需求声明要求 UnsupportedOperationError，并已配置 expected_error。
但 [test_send_message_to_terminal_task](https://github.com/a2aproject/a2a-tck/blob/263b9cfaf16a554bdfb166a7ba5b67716e946349/tests/compatibility/core_operations/test_task_lifecycle.py#L250)
只根据 `response.success` 判断，未调用已有的 expected-error 校验器。
因此，“拒绝了请求”被误当成“返回了规定的错误”。

回放五种响应：正确错误通过，另外三种错误响应在原测试中误通过，成功响应被拒绝。
候选补丁改用 `validate_expected_error(response, transport, expected_error_of(req))`；
同一组回放中仅正确错误通过。五个判断均与 Lean 检查器一致。

补丁：[tck-terminal-error.patch](../contributions/tck-terminal-error.patch)。
补丁包含五个回归测试，已对内存中的补丁版本运行并全部通过。
已通过 `git apply --check`，未修改上游 checkout、未提交 commit 或 PR。
随后已在独立工作副本完成全套 lint 和单元测试：281 项全部通过，见 [第一步验证记录](validation-step1.md)。
随后已在真实网络 SUT 上通过 JSON-RPC 的 CORE-SEND-002 测试，见 [第二步验证记录](validation-step2.md)。
未运行完整兼容性测试套件。

## 其它覆盖观察

这些是源代码审计发现，不都已经用反例复现：

- 终态 followup 测试通过 `create_completed_task` 设置前提，没有按四种终态参数化。
- `CORE-MULTI-005` 检查 followup 是否成功，但未比较返回的 contextId 与原值。
- `CORE-MULTI-006` 使用 completed 任务测试错误 context；终态本身也要求拒绝，可能掩盖 context 校验缺失。
- 中断恢复并非完全没有覆盖：`create_multiturn_task` 及 history helper 已执行 input-required → followup → completed。
  因此本项目后续应加强身份关联和断言，而不是宣称首次添加恢复测试。

参考：[生命周期测试](https://github.com/a2aproject/a2a-tck/blob/263b9cfaf16a554bdfb166a7ba5b67716e946349/tests/compatibility/core_operations/test_task_lifecycle.py)、
[任务辅助流程](https://github.com/a2aproject/a2a-tck/blob/263b9cfaf16a554bdfb166a7ba5b67716e946349/tests/compatibility/_task_helpers.py)。

## 真实 SDK 观察

进程内调用默认 V2 handler，共六个场景：四种预置终态、一次 input-required 恢复、一次非终态 context 冲突。
六条归一化轨迹全部通过 Lean。四种终态均返回 UnsupportedOperationError，executor 调用次数为 0；
恢复场景调用 executor 两次，冲突场景只调用初始的那一次。

终态场景的 SDK 后台 task 清理现象单独记录在 [实验说明](../integration/README.md)，不混同协议检查结论。

## 下一项可执行工作

独立工作副本的全套 lint/unit 检查及目标 JSON-RPC 网络测试已完成。下一步整理上游 PR 材料并核对是否已有同类修复。
随后分别处理 context 断言与四种终态覆盖；保持每个贡献范围小、需求依据明确。
