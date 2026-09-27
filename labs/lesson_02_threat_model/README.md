# 第 02 讲：AI 安全威胁模型

本实验直接分析 `lesson-01-prompt-injection` 标签对应的 Agent。它把系统范围、参与者、资产、组件、信任边界、数据流和威胁保存成 TOML，再由 Python 校验并生成 Markdown 报告。

这一步只回答“系统里有什么、数据怎样流动、可能被谁怎样利用、后续要补什么控制”。它不会提前实现 Prompt Guard、Policy Engine、任务 Scope、人工审批或 Sandbox。

## 文件位置

```text
labs/lesson_02_threat_model/
├── model/
│   ├── scope.toml          # 系统范围与建模假设
│   ├── inventory.toml      # 参与者、组件、资产和信任边界
│   ├── data_flows.toml     # 跨组件的数据流
│   └── threats.toml        # 威胁、安全需求和验证计划
└── generated/
    └── threat_model_report.md
```

关键实现位于 `src/agent_security/threat_model/`：

- `loader.py` 把四个 TOML 文件加载为不可变 Python 对象；
- `validator.py` 检查编号、引用、源码路径、真实工具清单和高优先级威胁覆盖；
- `renderer.py` 生成表格、Mermaid 数据流图和威胁详情；
- `__main__.py` 提供 validate、render、check 三个命令。

## 运行命令

```bash
make threat-model-validate
make threat-model-render
make threat-model-check
make lesson-02
```

`validate` 检查结构化模型，`render` 重新生成报告，`check` 检查报告是否已经过期。`lesson-02` 会依次校验模型、检查报告并运行全部课程测试。

## 一个可观察的错误练习

把 `data_flows.toml` 中任意一条数据流的资产临时改成不存在的 `AST-999`，再运行：

```bash
make threat-model-validate
```

校验器会报告 `TM021`，指出这条数据流引用了不存在的资产。完成观察后撤销临时修改。这个练习说明：威胁模型不是只供阅读的图片，它能像代码一样被自动检查。
