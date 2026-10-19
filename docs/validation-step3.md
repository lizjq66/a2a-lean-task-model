# 第三步：上游查重与 PR 草稿

核对日期：2026-10-18（America/Toronto；UTC 2026-10-19）。

结论：本次查询范围内未发现覆盖该断言修复的现有 PR。用户随后授权发布，已创建 [上游 PR #256](https://github.com/a2aproject/a2a-tck/pull/256)。

发布分支：`lizjq66:fix/terminal-task-expected-error`；提交：`7efb6d3`。发布前再次确认上游 main 未变，并重新运行 `make lint unit-test`：lint 通过，281 passed in 6.15s。实际提交仅包含候选补丁中的两个 Python 测试文件。

## 当前基线

通过 GitHub API 核对 [main](https://github.com/a2aproject/a2a-tck/commits/main) 仍为 `263b9cfaf16a554bdfb166a7ba5b67716e946349`，与前两步验证的基线一致。
补丁内容未变，SHA-256 为 `51ce1524f7a25fe184659b687dfb9d072ea1676e733dbf010dad77b3261da554`。

检索了所有状态下包含 `CORE-SEND-002` 的 PR、包含 `terminal` 和 `error` 的 PR，以及当时全部 26 个 open PR 的标题与说明；对下列相关 PR 进一步核对状态和差异。检索结果只代表此次检查时点。

| 上游工作 | 状态及与本补丁的关系 |
| --- | --- |
| [#150](https://github.com/a2aproject/a2a-tck/pull/150) | 已合并；声明 CORE-SEND-002 的 expected_error，未修改其专用测试断言 |
| [#165](https://github.com/a2aproject/a2a-tck/pull/165) | 已合并；避免通用 runner 执行缺少前置任务的测试 |
| [#207](https://github.com/a2aproject/a2a-tck/pull/207) | 已合并；强化 cancel、subscribe 等错误断言，遗漏本次 send-to-terminal 路径 |
| [#232](https://github.com/a2aproject/a2a-tck/pull/232) | open；更新 v1.0.1 错误映射，不修改本次生命周期测试 |
| [#247](https://github.com/a2aproject/a2a-tck/pull/247) | open；增加可选 caller/history profile，不修改本次生命周期测试 |

## 必须保留的版本边界

本项目 Lean 模型参照 A2A v1.0.1；当前 TCK 的 `specification/version.json` 仍指向 v1.0.0。
上游 [#240](https://github.com/a2aproject/a2a-tck/issues/240) 跟踪整体升级，#232 已提出错误映射更新。
其中 UnsupportedOperationError 的 gRPC 映射从 UNIMPLEMENTED 改为 FAILED_PRECONDITION。

本补丁复用现有 registry，不另行复制或修改错误码。它会随映射更新而变化，但不能把当前基线的 gRPC 断言称为已验证的 v1.0.1 行为。
HTTP+JSON 共用 HTTP 状态码的歧义也仍然存在。现有回归和网络证据明确限定为 JSON-RPC。

## 投稿材料

- [PR 标题](../contributions/pr-title.txt)
- [英文 PR 正文](../contributions/pr-body.md)
- [两文件补丁](../contributions/tck-terminal-error.patch)
- [完整 lint / 单元验证](validation-step1.md)
- [真实网络验证](validation-step2.md)

草稿记录了具体误判、五个回归结果、281 个单元测试，以及单条真实网络测试的边界。
没有将 Lean 工具链加入上游依赖；Lean 用于发现、复现和解释缺口，上游只接收常规 Python 修复。

PR 已正式发布，下一步关注上游 CI 和维护者反馈。
实际 commit 前已按上游 AGENTS.md 询问关联 GitHub issue；发布时未收到具体编号，未添加自动关闭 issue 的引用。
