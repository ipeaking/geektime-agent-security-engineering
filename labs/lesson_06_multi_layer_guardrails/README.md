# 第 06 讲实验：多层 AI Guardrails

本实验复用第 05 讲 Prompt Firewall 作为 Input Guard，并在其后增加 Context Guard、窄版 Tool Proposal Guard 和合成 Canary Output Guard。全部 Scenario 使用确定性 Replay，不调用外部模型，不读取真实文件，也不执行真实工具副作用。

## 运行

```bash
make PYTHON=.venv/bin/python guardrails-validate
make PYTHON=.venv/bin/python guardrails-render
make PYTHON=.venv/bin/python guardrails-check
make PYTHON=.venv/bin/python guardrails-evaluate
make PYTHON=.venv/bin/python lesson-06
```

查看单个 Trace：

```bash
PYTHONPATH=src .venv/bin/python -m agent_security.guardrails \
  run --scenario GR-SCENARIO-03
```

## 解释边界

- `Replay` 中的 `ToolCall` 是测试输入，不证明对应内容曾让真实模型提出该动作。
- Tool Proposal Guard 只演示“模型提议不等于系统批准”，不是完整的 RBAC、ABAC 或 Execution Policy Engine。
- Output Guard 只精确匹配合成 Canary，不是生产级 DLP 或 Secret Scanner。
- `NOT_RUN` 表示前层已阻断，`NOT_APPLICABLE` 表示没有对应对象；二者均不等于 `PASS`。
- 生成矩阵和文章结论应来自 `generated/` 中的确定性 Trace，而不是手工改写数字。

## 确定性结果

`generated/` 包含 Scenario 目录、防御矩阵、逐阶段 Trace、结构化 JSON 和 Mermaid 管线。文件不记录时间戳、绝对路径、工具参数或合成 Canary 原值，可由 `render` 逐字重建。
