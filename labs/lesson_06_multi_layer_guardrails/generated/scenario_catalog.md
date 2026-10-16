# Scenario Catalog

| Scenario | 场景 | Segment | Replay Tool | Output |
| --- | --- | ---: | --- | --- |
| GR-SCENARIO-01 | 正常摘要 | 1 | load_content | yes |
| GR-SCENARIO-02 | 显式读取并外发 | 1 | - | no |
| GR-SCENARIO-03 | 英文委婉改写 | 1 | read_file | no |
| GR-SCENARIO-04 | 中文委婉改写 | 1 | read_file | no |
| GR-SCENARIO-05 | Base64 Payload | 1 | read_file | no |
| GR-SCENARIO-06 | 跨段读取与外发 | 2 | - | no |
| GR-SCENARIO-07 | 来源标签伪造与敏感工具提议 | 1 | read_file | no |
| GR-SCENARIO-08 | 合成 Canary 输出泄露 | 1 | load_content | yes |

> Replay 是确定性测试输入，不代表真实模型曾在这些内容下提出对应工具调用。
