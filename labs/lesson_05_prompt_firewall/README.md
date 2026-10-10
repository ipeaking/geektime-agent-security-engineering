# 第 05 讲：第一版 Prompt Firewall

本讲在第 04 讲 `ContentEnvelope` 与 Agent Context 之间加入确定性的内容风险扫描和准入决策：

```text
ContentEnvelope
→ Normalizer
→ Rule Detectors
→ Risk Scorer
→ RiskAssessment
→ ContentAdmissionPolicy
→ GuardResult
→ PromptFirewallMiddleware
```

`ContentAdmissionPolicy` 只决定外部内容能否进入当前模型上下文。后续 `Execution Policy Engine` 才负责决定模型提出的 `ToolCall` 是否获得用户和任务授权；两者不是同一个边界。

## 决策语义

- `ALLOW`：原始 `ContentEnvelope` 可以进入模型；
- `FLAG`：原文继续进入模型，`GuardResult` 只保存在程序侧，不拼接到正文；
- `BLOCK`：enforce 模式不转发正文，observe 模式仍转发但记录阻断判断。

Firewall 不重写 `envelope.content`。规范化文本只在扫描期间存在，报告只保存内容哈希、限长脱敏证据、脱敏前匹配片段的 SHA-256 和规范化位置，不保存证据原值之外的上下文窗口。

风险分数按类别去重：同一类别命中多条规则时只取最高权重，再添加明确记录的组合风险分。它是当前规则集和准入策略下的工程分值，不是攻击概率、恶意概率或模型安全概率。

## 规则语言与限制

第一版只支持 `literal` 和 `bounded_terms`，不允许用户动态提交 Regex。规则和策略必须来自版本控制中的可信 TOML。扫描前限制内容长度，每条规则还限制证据数量和长度。

超过 `max_content_chars` 时不静默截断，也不进行部分扫描：`scan_status=INCOMPLETE`、`risk_score=0`，由准入策略以 `content_length_exceeded` 原因作出 `BLOCK`。这属于扫描失败策略，不是假装内容规则得到了 100 分。

第一版不实现 Base64、Hex、ROT13 解码、自然语言翻译、复杂同形字符分析、跨轮检测、LLM Judge、Tool Permission、Human Approval 或生产级 DLP。

## 评测集

固定数据集包含 32 个 Case：

- CONTRACT：12 个核心行为契约，失败会阻断严格评测；
- EVALUATION：12 个边界与误报控制样本，用于描述性指标；
- CHALLENGE：8 个绕过样本，不进入构建 Gate。

`intent_label` 描述样本场景意图，`expected_decision` 描述内容准入期望。安全教程可以是 `BENIGN + FLAG`：作者没有恶意，但其中的命令式攻击文本仍值得程序侧标记。

报告同时给出 EVALUATION 的 ALLOW/FLAG/BLOCK 三分类混淆矩阵。Precision、Recall 和 F1 则以“期望或实际决策是否属于 FLAG/BLOCK”定义正样本，只描述本讲固定样本，不代表未知输入的泛化能力或生产准确率。

## 第 04 讲集成

评测直接调用第 04 讲现有 Loader、Builder 和四类 Adapter，构建四个 Clean 与四个 Injected `ContentEnvelope`，不复制 Fixture：

- 四个 Clean Envelope 预期 `ALLOW`；
- 四个 Injected Envelope 预期命中相同核心类别并 `BLOCK`；
- Firewall 只扫描 `envelope.content`，不会根据内部 `source_ref`、`fixture_name` 或文件名分组。

集成基线为 `v0.4.2-lesson-04-indirect-prompt-injection`。

## 运行

```bash
make PYTHON=.venv/bin/python prompt-firewall-validate
make PYTHON=.venv/bin/python prompt-firewall-demo
make PYTHON=.venv/bin/python prompt-firewall-render
make PYTHON=.venv/bin/python prompt-firewall-check
make PYTHON=.venv/bin/python prompt-firewall-evaluate
make PYTHON=.venv/bin/python lesson-05
```

扫描单个 Case：

```bash
PYTHONPATH=src .venv/bin/python -m agent_security.prompt_firewall scan \
  --case PF-CONTRACT-003
```

扫描用户明确指定的本地文本文件：

```bash
PYTHONPATH=src .venv/bin/python -m agent_security.prompt_firewall scan \
  --file path/to/content.txt --source-type web
```

## 确定性输出

`generated/` 包含：

- `case_catalog.md`；
- `evaluation_report.md`；
- `evaluation_results.json`；
- `rule_coverage.md`；
- `firewall_pipeline.mmd`。

这些文件不包含时间戳、绝对路径、API Key、完整规范化文本或模型输出。`check` 会在内存中重新生成并逐字比较。

## 本版本的确定性结果

在 `v0.5.0-lesson-05-prompt-firewall` 发布前执行上述命令，结果为：

- Contract：12/12；
- Evaluation 精确决策：12/12；
- 第 04 讲 Carrier 集成：8/8；
- 固定 Evaluation 集上的 Precision、Recall、F1：均为 1.000；
- Challenge：8 个样本中识别 5 个，漏过英文委婉改写、Base64 和中文委婉改写 3 个；
- `make lesson-05`：全部 109 项课程测试通过。

Challenge 的漏检是第一版能力边界的组成部分，不进入严格 Gate。固定样本上的 1.000 也不是生产环境准确率；它只说明当前实现与版本控制中的期望一致。
