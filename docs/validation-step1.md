# 第一步：独立 TCK 工作副本验证

日期：2026-10-18。结果：**完整 lint 通过，281 个单元测试全部通过**。

## 验证对象

- TCK 基线：`263b9cfaf16a554bdfb166a7ba5b67716e946349`。
- 独立工作副本：`/private/tmp/a2a-tck-validation-20261018`。
- 补丁：[tck-terminal-error.patch](../contributions/tck-terminal-error.patch)。
- 补丁 SHA-256：`51ce1524f7a25fe184659b687dfb9d072ea1676e733dbf010dad77b3261da554`。
- 上游 `uv.lock` SHA-256：`7650dafd015617312c49f87bfafaa17e96f6af5d7d73540ce0ef4a2f46dfe404`，未修改。
- 环境：macOS arm64，CPython 3.11.15，pytest 9.0.2，ruff 0.15.5。

环境使用上游锁文件，通过 `uv sync --locked --extra dev` 安装。
与先前集成实验的 Python 环境分离，避免依赖版本差异影响结果。

## 最终验证

在工作副本执行上游 Makefile 的实际目标，`UV_NO_SYNC=1` 保持已锁定安装的 dev 环境，
`UV_OFFLINE=1` 禁止测试期间自动联网解析依赖：

```sh
UV_NO_SYNC=1 UV_OFFLINE=1 make lint
UV_NO_SYNC=1 UV_OFFLINE=1 make unit-test
git diff --check
```

| 检查 | 结果 |
| --- | --- |
| 完整 `make lint` | All checks passed |
| 完整 `make unit-test` | 281 passed in 6.65s，无 skip/failure/error |
| 新增错误类型回归 | 五个参数化用例全部通过，包含在 281 项中 |
| 补丁在干净基线 `git apply --check` | 通过 |
| 工作副本 `git diff --check` | 通过 |
| 归档回归文件与工作副本比较 | 内容完全一致 |

工作副本的变更只有生命周期测试中的错误校验替换，以及新增的单元测试文件。
未提交 commit 或 PR。

## 过程中处理的问题

首次 lint 指出新增回归测试缺少参数/返回类型标注，以及调用次数断言中的魔法数字。
已补齐类型，并用响应序列长度表达预期调用次数；修正已同步回归档补丁和生成源文件。

首次单元测试在沙箱内运行，271 项通过；另外 8 个失败与 2 个 setup error 均因
本地 HTTP/Webhook 服务绑定端口被禁止。经授权在沙箱外重跑同一个完整目标后，
281 项全部通过；没有跳过测试或修改上游服务代码。

## 下一步

第二步是启动真实 Python SDK 网络服务，通过 JSON-RPC 验证修改后的终态测试。
本记录只确认第一步完成，不把单元测试内的本地 HTTP 服务当成 SDK 网络端到端验证。
