# 规则依据与证明边界

基线核对日期：2026-10-18。

- A2A：`v1.0.1`，commit `3303592588e388e62e0f69f701af531d2f4e3991`。
- TCK：`263b9cfaf16a554bdfb166a7ba5b67716e946349`。已审计此 checkout 的生命周期测试及相关需求、辅助流程，并定向回放 CORE-SEND-002；未运行全套 TCK。详见 [审计结果](tck-findings.md)。
- Lean：`leanprover/lean4:v4.34.0`，无第三方 Lean 依赖。

## 范围

第一版检查**单个已存在任务的、按因果顺序归一化的有限观察轨迹**。
初始快照作为输入前提，不验证任务创建过程。每个 followup 是已经结束的
SendMessage 请求/响应交换，目标就是该任务。后续 snapshot 是可信顺序中的最新观察。
本模型不接受混合多个任务、延迟到达的旧快照或并发请求作为同一条有序轨迹。

PASS 仅表示没有违反已建模规则。它不证明完整 A2A 合规，不证明轨迹完整，也不证明任务最终完成。
没有事件的轨迹和停留在中断态的轨迹都是合法前缀。

## 规则表

| 本地规则 | 来源与性质 | 当前检查 | 现有 TCK 线索 |
| --- | --- | --- | --- |
| TERMINAL-STABILITY | [v1.0.1 生命周期说明：Task Immutability](https://github.com/a2aproject/A2A/blob/3303592588e388e62e0f69f701af531d2f4e3991/docs/topics/life-of-a-task.md#task-immutability)，解释性生命周期约束 | 进入终态后，后续快照必须保留相同状态；重复读取允许 | 需要审计跨快照覆盖，不能据此断言 TCK 缺失 |
| TERMINAL-MESSAGE | [规范 §3.1.1](https://github.com/a2aproject/A2A/blob/3303592588e388e62e0f69f701af531d2f4e3991/docs/specification.md#311-send-message)，终态消息错误要求 | context 未冲突时，终态 followup 返回 UnsupportedOperationError | CORE-SEND-002 |
| CONTEXT-MISMATCH | [规范 §3.4.3](https://github.com/a2aproject/A2A/blob/3303592588e388e62e0f69f701af531d2f4e3991/docs/specification.md#343-multi-turn-conversation-patterns)，MUST 拒绝 | 冲突 context 不得得到 accepted；不限定错误优先级 | CORE-MULTI-006 |
| CONTEXT-IDENTITY | 单任务模型中 context 固定的建模前提，依据 §3.4.3 的任务/context 关联语义 | 后续快照保持原 context | CORE-MULTI-005 涉及推断；当前未验证全部响应关联规则 |
| PROFILE-TASK-IDENTITY | **本工具单任务输入范围约束**，不是独立的协议违规结论 | 快照不得切换到另一 taskId | 多任务需另建轨迹 |
| 中断后继续 | §3.4.3 的 input-required 模式；[proto 的中断态定义](https://github.com/a2aproject/A2A/blob/3303592588e388e62e0f69f701af531d2f4e3991/specification/a2a.proto) | 允许恢复轨迹；不强制接受消息、必须经过 working 或最终完成 | 已有 input-required 场景，完整恢复链覆盖待核实 |

状态集合包含 UNSPECIFIED。它不是终态，不能强行归为 working 或视为无效输入；本版本不替规范增加其转换限制。

## 有意保留的不确定性

- 不构造完整状态转换白名单。非终态接受/拒绝追加消息均不在此片段内判错。
- 当“终态”与“context 冲突”同时出现时，只要求拒绝，不臆造错误优先级。
- AUTH_REQUIRED 与 INPUT_REQUIRED 都属于中断态，但当前不验证凭据、认证回调或恢复触发机制。
- 阻塞模式与流关闭的细节暂不纳入；需先对齐规范不同章节，再决定可移植的断言。
- 任务复活、运行时追加消息和取消竞争跟踪 [A2A #1992](https://github.com/a2aproject/A2A/issues/1992)。开放提案不作为 v1.0.1 合规规则。

## 已证明的内容

`A2A/Proofs.lean` 使用 Lean 内核检查证明，没有 `sorry` 或自定义公理：

- `check_iff_valid` / `check_sound` / `check_complete`：布尔检查器与独立声明的 ValidTrace 归纳关系等价。
- `allowed_preserves_terminal` / `terminal_stable`：在模型允许的步与任意有限合法后续轨迹中，原终态保持不变。
- `violation_none_iff` / `diagnose_none_iff`：带规则诊断的实现和声明式语义一致。
- `diagnose_first`：诊断索引之前的事件均允许，该位置违反返回的规则。
- `input_resumption_valid`：给出同一任务从 input-required 经补充输入恢复并完成的合法轨迹；这不是必然完成的承诺。

这些证明相对于 `Allowed` 的定义成立。自然语言到模型的翻译、JSON 解析器、
日志采集与排序、Lean 编译器生成的可执行代码、SDK 和网络行为均未在此项目中形式验证。
终态证明只涉及状态值；不涵盖 artifacts/history 的内容不可变性。

## 下一步 TCK 对接

已完成上述 TCK commit 的首次定向审计，并生成 CORE-SEND-002 的错误类型断言补丁。
复用已有需求 ID，不新造上游 ID，也不把本地规则名伪装成上游需求。

| 候选测试 | 设置与刺激 | 预期观察 | 提交前还需要什么 |
| --- | --- | --- | --- |
| 四种终态下追加消息 | 分别建立 completed/failed/canceled/rejected 任务，发送同 ID 消息 | 相应 UnsupportedOperationError，后续仍保留原终态 | 查明 CORE-SEND-002 的参数覆盖及各终态的可控构造方式 |
| input-required 完整往返 | 确定性 executor 请求输入，客户端补充输入 | 同一任务恢复；用该场景约定检查结果 | 明确 executor 契约，避免把特定业务行为升级成通用 MUST |
| 中断恢复中的 context 关联 | 分别省略 context 与提供错误 context | 推断原 context，或拒绝冲突 | 对照 CORE-MULTI-005/006，避免重复已有测试 |
| 终态后重复查询 | 多次 GetTask | 相同终态，不误判为状态变化 | 接入现有查询 fixture |

第一版 fixtures 是**归一化模型用例**，不是已可直接运行的官方 TCK 测试。
现已新增 [集成实验](../integration/README.md)，可从真实 SDK handler 生成轨迹并回放上游测试断言。
对接时先使用受控服务保证观察顺序；不要把跨连接乱序日志直接交给本检查器。
