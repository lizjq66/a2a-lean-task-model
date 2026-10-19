# 第二步：真实 JSON-RPC 网络验证

验证日期：2026-10-18（America/Toronto）；TCK 报告时间为 2026-10-19 00:47 UTC。

结果：**修改后的终态消息测试通过，真实网络观察生成的轨迹也通过 Lean 检查。**

## 验证配置

- TCK：`263b9cfaf16a554bdfb166a7ba5b67716e946349`，独立工作副本应用候选补丁。
- 补丁 SHA-256：`51ce1524f7a25fe184659b687dfb9d072ea1676e733dbf010dad77b3261da554`，与第一步相同。
- Python SDK：`01da00b0951ba6201af860d17b4c088be7902d43`。
- SUT：真实 SDK DefaultRequestHandlerV2、InMemoryTaskStore、JSON-RPC routes；复用该 TCK commit 未修改的生成式 TckAgentExecutor。
- 服务包装：本项目 `integration/network_sut.py`，只开放 JSON-RPC 与 Agent Card，监听 `127.0.0.1` 随机端口。
- 网络依赖：Starlette 1.9.0、sse-starlette 3.5.0、Uvicorn 0.54.0；完整运行依赖见 `integration/requirements.txt`。
- TCK 测试仍使用第一步按上游锁文件安装的独立环境。

没有修改 SDK、生成式 executor 或候选补丁来使测试通过。

## 实际执行与结果

运行入口：

```sh
.venv/bin/python integration/run_network.py /private/tmp/a2a-tck-validation-20261018
```

脚本验证补丁已应用、启动临时服务、获取 Agent Card，然后从 TCK 根目录执行：

```sh
UV_NO_SYNC=1 UV_OFFLINE=1 uv run ./run_tck.py \
  --sut-host http://127.0.0.1:54099 --transport jsonrpc --level must -v -- \
  -k 'test_send_message_to_terminal_task and jsonrpc'
```

端口由本次运行动态选择，复现时不要求仍使用 54099。

- pytest：**1 passed, 264 deselected**，0 skipped。
- `CORE-SEND-002`：结构化报告为 PASS，`jsonrpc` 为 PASS，无 errors。
- 脚本校验 JUnit 中恰好一个测试且无 skip/failure/error，防止把前提未满足导致的跳过当成通过。

随后额外发出并保存四个真实 HTTP JSON-RPC 请求：

1. SendMessage：通过 `tck-complete-task` 场景创建并完成任务。
2. GetTask：观察到相同任务的 COMPLETED 状态。
3. SendMessage：引用该 taskId，省略 contextId；收到 JSON-RPC error code **-32004**。
4. GetTask：仍为原 taskId、原 contextId 和 COMPLETED 状态。

这组观察被归一化到 `trace.json`，实际调用 Lean 检查器，退出码 0。
临时服务已由脚本终止并等待退出；没有留下需要用户手动关闭的服务。

## 证据文件

生成文件保存在本地 `artifacts/network/`（gitignored，可通过脚本重建）：

- `exchanges.json`：上述四个请求与响应。
- `traffic.jsonl`：服务端捕获的 HTTP 交换，包括 TCK 测试流量。
- `trace.json`：交给 Lean 的归一化轨迹。
- `summary.json`：目标测试名称、命令、错误码及 Lean 结果。
- `sut.log`、`tck.log`：原始服务与测试日志。
- `reports/compatibility.json`、`reports/compatibility.html`、`reports/tck_report.html`、`reports/junitreport.xml`：上游报告。

## 结果的边界与附带观察

本次只验证 **JSON-RPC + COMPLETED** 的终态消息路径，没有跑全部 MUST 要求，
也没有把此前四种终态的 handler 测试扩展成四种终态的网络测试。

TCK 汇总页面把未运行要求计入了 Failed 总数，因此显示 0.8% compatibility。
逐要求 JSON 中这些项实际为 `NOT TESTED`，无测试 ID；本次运行的 CORE-SEND-002 为 PASS。
不能把这个汇总百分比解释成 SDK 只有 0.8% 合规，也不能据此宣称 128 项实际测试失败。

服务日志保留了 `Failed to detach context` 和 `Task was destroyed but it is pending`，
与此前 handler 实验观察的后台任务清理现象相关，但根因尚未确认。
没有屏蔽这些日志、修改 SDK 或把它们当成预期协议响应。
本次请求断言全部通过；这不意味着 SDK 的资源清理和遥测没有问题。

## 下一步

第三步整理上游 PR 的标题、问题说明、最小反例与验证证据。
发布前仍需核对上游当前分支是否已有同类修复，以及目标仓库的贡献要求。
