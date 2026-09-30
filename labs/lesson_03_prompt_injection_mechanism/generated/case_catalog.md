# Context Lab Case Catalog

> 自动生成，请勿手工修改。

| Case | 标题 | Channel | Prompt | Wrapper | 公共 Payload |
| --- | --- | --- | --- | --- | --- |
| CASE-01 | Clean Web | clean_web | neutral | none | — |
| CASE-02 | Inline Quoted Content | inline_quoted_content | neutral | none | fixtures/payloads/injection.txt |
| CASE-03 | Raw Web Content | webpage | neutral | none | fixtures/payloads/injection.txt |
| CASE-04 | Delimited Web Content | webpage | neutral | delimiter | fixtures/payloads/injection.txt |
| CASE-05 | Source-Labeled Web Content | webpage | neutral | source_label | fixtures/payloads/injection.txt |
| CASE-06 | Explicit Boundary Prompt | webpage | explicit_boundary | none | fixtures/payloads/injection.txt |

所有注入 Case 使用同一份 Payload；Case 只改变声明的入口、包装方式或 Prompt Profile。
