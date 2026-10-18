# 第 07 讲实验：Tool Risk Lab

这一讲严格对应课纲“当 AI 可以调用 Tool，风险发生了什么变化？”。实验不实现权限系统，而是用五个不触达真实外部系统的合成工具，对比错误文本与真实动作之间的风险差异。

```text
固定外部内容
→ 确定性 ToolCall Replay
→ SyntheticToolEnvironment
→ ToolEvent / Canary at Sink
```

五个工具分别模拟 `read_file`、`write_file`、`send_email`、`query_db` 和 `run_shell`。文件、数据库、Outbox 和 Shell Recorder 全部位于进程内存中；`run_shell` 只接受两条固定标识，不启动任何操作系统进程。

运行：

```bash
make PYTHON=.venv/bin/python tool-risk-validate
make PYTHON=.venv/bin/python tool-risk-render
make PYTHON=.venv/bin/python tool-risk-check
make PYTHON=.venv/bin/python tool-risk-evaluate
make PYTHON=.venv/bin/python tool-risk-demo
make PYTHON=.venv/bin/python lesson-07
```

`TR-SCENARIO-01` 只有错误文本，没有 ToolCall，因此没有执行效果。其余 Scenario 分别展示正常读取、文件外发、文件写入、数据库外发和 Shell 命令记录。带 Canary 的内容只有真正进入合成 Outbox，才记为 `canary_reached_sink=true`。每个 Scenario 都会创建独立的 `SyntheticToolEnvironment`，不会共享内存文件、Outbox、数据库或 Shell Recorder。

Replay 只用于稳定验证“如果候选 ToolCall 已经出现，执行器会造成什么效果”，不表示真实模型一定会在相同输入下提出这些调用。
