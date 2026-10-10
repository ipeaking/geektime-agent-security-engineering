# Carrier Lab Deterministic Matrix

> 自动生成，请勿手工修改。 该矩阵验证内容管线，不包含真实模型结论。

| Case | Carrier | Variant | Parser | 正常事实 | Payload | Source Ref |
| --- | --- | --- | --- | --- | --- | --- |
| CASE-01 | web | clean | WebContentAdapter/html.parser | present | absent | `fixtures/web/clean.html` |
| CASE-02 | web | injected | WebContentAdapter/html.parser | present | present | `fixtures/web/injected.html` |
| CASE-03 | pdf | clean | PdfContentAdapter/pypdf | present | absent | `fixtures/pdf/clean.pdf` |
| CASE-04 | pdf | injected | PdfContentAdapter/pypdf | present | present | `fixtures/pdf/injected.pdf` |
| CASE-05 | email | clean | EmailContentAdapter/email.parser | present | absent | `fixtures/email/clean.eml` |
| CASE-06 | email | injected | EmailContentAdapter/email.parser | present | present | `fixtures/email/injected.eml` |
| CASE-07 | rag_document | clean | RagContentAdapter/deterministic_keyword | present | absent | `fixtures/rag/clean.json` |
| CASE-08 | rag_document | injected | RagContentAdapter/deterministic_keyword | present | present | `fixtures/rag/injected.json` |
