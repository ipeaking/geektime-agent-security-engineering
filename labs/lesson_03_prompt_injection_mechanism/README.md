# 第 03 讲：Prompt Injection 为什么这么难防？

这一讲从第 02 讲的 `TB-002`、`TB-003` 和 `TB-004` 继续向下分析。我们不再制造一次数据外传，而是搭建 Context Lab，用同一段注入载荷观察内容入口、文本包装和 System Prompt 是否会改变模型的工具决策。

## 本讲目标

当 System Prompt、用户任务、网页和工具结果都以自然语言进入上下文时，模型需要区分“应该遵循的指令”和“只需要分析的数据”。Context Lab 把这种差别显式记录为 `source`、`trust`、`intended_role` 和 `transport`，再把真实模型行为单独作为非确定性观察。

## 为什么从第 02 讲继续

第 02 讲已经指出：不可信内容进入上下文、模型服务返回提议、模型提议进入执行层，是三条不同的信任边界。第 03 讲专门检查前两条边界如何影响模型决策，但不会修改第 01 讲故意缺少授权的 `ToolExecutor`，也不会提前实现后续课程的防御。

## 六个控制变量 Case

| Case | 内容入口或变化 | 作用 |
| --- | --- | --- |
| CASE-01 | 正常网页 | 建立摘要基线 |
| CASE-02 | 用户消息中的引用材料 | 观察同一条消息里指令与数据的混合 |
| CASE-03 | 原始网页正文 | 建立间接注入基线 |
| CASE-04 | 网页 Payload 外加分隔符 | 观察分隔符信号 |
| CASE-05 | 网页 Payload 外加来源标签 | 观察来源与信任标签信号 |
| CASE-06 | 原始网页配合明确边界 Prompt | 观察 System Prompt 信号 |

五个注入 Case 都引用 `fixtures/payloads/injection.txt`。CASE-03、CASE-04、CASE-05 只改变 Wrapper；CASE-06 相对 CASE-03 只改变 Prompt Profile。Validator 会自动检查这些约束，避免实验在不知不觉中换了攻击内容。

## Inspect 与 Live 的区别

`inspect` 不调用模型，也不访问外部网络。它确定性地展示 Case 如何构建，以及每段内容的来源、信任级别、意图角色、传输方式、哈希和限长预览，因此可以进入 CI。

`live` 会调用真实模型，观察模型是否完成正常摘要、是否提出 `read_file` 或 `send_diagnostic`。结果可能随模型、版本和运行发生变化，所以不进入默认 CI，也不能被解释成固定攻击成功率。

## Observation Executor

Live 中的 Observation Executor 是实验测量装置：`fetch_webpage` 只允许访问本次运行创建的 `http://127.0.0.1:<随机端口>`；第一次出现 `read_file` 或 `send_diagnostic` 时，只记录提议并立即停止，不读取文件，也不发送数据。未知工具同样停止并记录。

它不是生产安全防御，不是 Policy Engine，也没有实现正式的 Tool Permission。它只让本讲能够在不重复制造敏感副作用的情况下测量模型提议。

## 确定性生成文件

`generated/` 中包含：

```text
case_catalog.md     六个 Case 的目录
context_traces.md   每个 ContextItem 的来源、角色、哈希和预览
context_flow.mmd    内容进入上下文并形成 ToolCall 的 Mermaid 图
```

这些文件不包含时间、随机值、本机路径、API Key 或 Live 结果。`check` 会在内存中重新生成并逐字比较。

## 运行命令

先运行不需要 API Key 的确定性命令：

```bash
make context-lab-inspect
make context-lab-render
make context-lab-check
make lesson-03
```

只检查一个 Case 时，可以直接运行：

```bash
PYTHONPATH=src python -m agent_security.context_lab inspect --case CASE-03
```

确认 `.env` 已配置真实模型后，再手工运行：

```bash
make context-lab-live
make context-lab-report
```

也可以指定 Case、次数和模型：

```bash
PYTHONPATH=src python -m agent_security.context_lab live \
  --case CASE-03 \
  --repeat 3 \
  --model deepseek-v4-pro
```

## Live 数据和输出位置

Live 会把合成任务、System Prompt 和合成网页内容发送给外部模型服务。不要在 Payload、页面、Prompt 或任务中放入真实凭证、个人数据、企业文档或生产日志。

经过裁剪的客观结果写入：

```text
.lab-output/lesson-03/
├── live_runs.jsonl
├── observation_matrix.md
├── observation_matrix.csv
└── runs/
```

`.lab-output/` 已被 Git 忽略。记录中不保存隐藏推理、API Key、请求 Header 或真实敏感数据。

一次没有出现敏感工具提议，不等于系统已经安全；一次出现提议，也不代表固定攻击成功率。报告只统计完成次数、敏感工具提议、正常事实命中和错误，不使用另一个模型充当裁判。

## 本讲没有实现的能力

Context Lab 没有实现 Prompt Firewall、Task Scope、Tool Permission、Policy Engine、Human Approval 或完整的 Context Isolation。分隔符、来源标签和明确 Prompt 都只是提供给模型的文本信号，不能代替执行层授权。

下一讲会把相同问题扩展到网页、PDF、邮件和 RAG 等载体，继续分析间接 Prompt Injection 如何进入 Agent；真正的权限和执行层边界会在后续课程中逐步实现。
