# 第 08 讲实验：Tool Permission System

这一讲严格对应课纲“不要相信模型：实现 Tool Permission System”。它给工具标注 `READ`、`WRITE`、`EXECUTE`、`NETWORK`、`PAYMENT` 和 `ADMIN` 六类能力，并在调用前检查可信 Subject、TaskContract、工具白名单与 Capability。

```text
Candidate ToolCall + Trusted Subject + TaskContract
→ PolicyEnforcedToolExecutor
→ Request Validation
→ Tool Registration
→ Subject Role
→ Task Tool Allowlist
→ Capability Allowlist
→ ALLOW / DENY
→ 只有 ALLOW 调用 Recording Delegate
```

运行：

```bash
make PYTHON=.venv/bin/python tool-permission-validate
make PYTHON=.venv/bin/python tool-permission-render
make PYTHON=.venv/bin/python tool-permission-check
make PYTHON=.venv/bin/python tool-permission-evaluate
make PYTHON=.venv/bin/python tool-permission-demo
make PYTHON=.venv/bin/python lesson-08
```

本讲不实现资源实例 Scope、目的地细分或人工审批。它们属于后续课纲，不应提前混入第一版 Tool Permission System。
