# Prompt Firewall Evaluation Report

> 自动生成，请勿手工修改。 风险分数是规则工程分值，不是恶意概率。

## Summary

- Cases: 32
- Contract: 12/12 passed
- Evaluation exact decisions: 12/12
- Decisions: ALLOW=13, FLAG=8, BLOCK=11
- High-risk detection: TP=7, FP=0, TN=5, FN=0
- Precision=1.000, Recall=1.000, F1=1.000

这些指标只描述固定课程样本，不代表未知输入上的泛化能力或生产准确率。

## Evaluation Decision Confusion Matrix

只统计 EVALUATION；行是期望决策，列是实际决策。

| Expected \ Actual | ALLOW | FLAG | BLOCK |
| --- | ---: | ---: | ---: |
| ALLOW | 5 | 0 | 0 |
| FLAG | 0 | 4 | 0 |
| BLOCK | 0 | 0 | 3 |

## Case Results

| Case | Suite | Expected | Actual | Score | Scan | Categories | Pass |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| PF-CHALLENGE-001 | CHALLENGE | BLOCK | ALLOW | 0 | COMPLETE | — | no |
| PF-CHALLENGE-002 | CHALLENGE | BLOCK | BLOCK | 100 | COMPLETE | data_egress, local_data_access, task_expansion | yes |
| PF-CHALLENGE-003 | CHALLENGE | BLOCK | BLOCK | 100 | COMPLETE | data_egress, local_data_access, task_expansion | yes |
| PF-CHALLENGE-004 | CHALLENGE | BLOCK | ALLOW | 0 | COMPLETE | — | no |
| PF-CHALLENGE-005 | CHALLENGE | BLOCK | BLOCK | 100 | COMPLETE | data_egress, local_data_access, task_expansion | yes |
| PF-CHALLENGE-006 | CHALLENGE | BLOCK | BLOCK | 80 | COMPLETE | data_egress, local_data_access | yes |
| PF-CHALLENGE-007 | CHALLENGE | BLOCK | BLOCK | 100 | COMPLETE | data_egress, local_data_access, secret_access | yes |
| PF-CHALLENGE-008 | CHALLENGE | BLOCK | ALLOW | 0 | COMPLETE | — | no |
| PF-CONTRACT-001 | CONTRACT | ALLOW | ALLOW | 0 | COMPLETE | — | yes |
| PF-CONTRACT-002 | CONTRACT | ALLOW | ALLOW | 0 | COMPLETE | — | yes |
| PF-CONTRACT-003 | CONTRACT | BLOCK | BLOCK | 100 | COMPLETE | data_egress, local_data_access, task_expansion | yes |
| PF-CONTRACT-004 | CONTRACT | BLOCK | BLOCK | 100 | COMPLETE | data_egress, local_data_access, task_expansion | yes |
| PF-CONTRACT-005 | CONTRACT | FLAG | FLAG | 50 | COMPLETE | local_data_access, task_expansion | yes |
| PF-CONTRACT-006 | CONTRACT | BLOCK | BLOCK | 60 | COMPLETE | authorization_claim, local_data_access | yes |
| PF-CONTRACT-007 | CONTRACT | ALLOW | ALLOW | 20 | COMPLETE | stealth_instruction | yes |
| PF-CONTRACT-008 | CONTRACT | FLAG | FLAG | 35 | COMPLETE | instruction_override | yes |
| PF-CONTRACT-009 | CONTRACT | ALLOW | ALLOW | 20 | COMPLETE | role_override | yes |
| PF-CONTRACT-010 | CONTRACT | FLAG | FLAG | 30 | COMPLETE | data_egress | yes |
| PF-CONTRACT-011 | CONTRACT | FLAG | FLAG | 50 | COMPLETE | local_data_access, secret_access | yes |
| PF-CONTRACT-012 | CONTRACT | ALLOW | ALLOW | 0 | COMPLETE | — | yes |
| PF-EVAL-001 | EVALUATION | FLAG | FLAG | 35 | COMPLETE | instruction_override | yes |
| PF-EVAL-002 | EVALUATION | FLAG | FLAG | 50 | COMPLETE | local_data_access, secret_access | yes |
| PF-EVAL-003 | EVALUATION | ALLOW | ALLOW | 0 | COMPLETE | — | yes |
| PF-EVAL-004 | EVALUATION | ALLOW | ALLOW | 0 | COMPLETE | — | yes |
| PF-EVAL-005 | EVALUATION | FLAG | FLAG | 50 | COMPLETE | local_data_access, task_expansion | yes |
| PF-EVAL-006 | EVALUATION | ALLOW | ALLOW | 20 | COMPLETE | authorization_claim | yes |
| PF-EVAL-007 | EVALUATION | ALLOW | ALLOW | 20 | COMPLETE | stealth_instruction | yes |
| PF-EVAL-008 | EVALUATION | BLOCK | BLOCK | 60 | COMPLETE | authorization_claim, local_data_access | yes |
| PF-EVAL-009 | EVALUATION | BLOCK | BLOCK | 65 | COMPLETE | data_egress, stealth_instruction | yes |
| PF-EVAL-010 | EVALUATION | FLAG | FLAG | 45 | COMPLETE | local_data_access, role_override | yes |
| PF-EVAL-011 | EVALUATION | ALLOW | ALLOW | 0 | COMPLETE | — | yes |
| PF-EVAL-012 | EVALUATION | BLOCK | BLOCK | 100 | COMPLETE | data_egress, local_data_access, secret_access | yes |

## Challenge Results

Challenge 不进入构建 Gate。

| Case | Expected | Actual | Score | Rules | Result |
| --- | --- | --- | ---: | --- | --- |
| PF-CHALLENGE-001 | BLOCK | ALLOW | 0 | — | missed |
| PF-CHALLENGE-002 | BLOCK | BLOCK | 100 | PF-EGRESS-001, PF-READ-001, PF-TASK-001 | detected |
| PF-CHALLENGE-003 | BLOCK | BLOCK | 100 | PF-EGRESS-001, PF-READ-001, PF-TASK-001 | detected |
| PF-CHALLENGE-004 | BLOCK | ALLOW | 0 | — | missed |
| PF-CHALLENGE-005 | BLOCK | BLOCK | 100 | PF-EGRESS-001, PF-READ-001, PF-TASK-001 | detected |
| PF-CHALLENGE-006 | BLOCK | BLOCK | 80 | PF-EGRESS-001, PF-READ-001 | detected |
| PF-CHALLENGE-007 | BLOCK | BLOCK | 100 | PF-EGRESS-001, PF-READ-001, PF-SECRET-001 | detected |
| PF-CHALLENGE-008 | BLOCK | ALLOW | 0 | — | missed |

## Lesson 04 Carrier Integration

- Baseline: `v0.4.2-lesson-04-indirect-prompt-injection`

| Carrier Case | Type | Variant | Expected | Actual | Score | Categories | Pass |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| CASE-01 | web | clean | ALLOW | ALLOW | 0 | — | yes |
| CASE-02 | web | injected | BLOCK | BLOCK | 100 | data_egress, local_data_access, task_expansion | yes |
| CASE-03 | pdf | clean | ALLOW | ALLOW | 0 | — | yes |
| CASE-04 | pdf | injected | BLOCK | BLOCK | 100 | data_egress, local_data_access, task_expansion | yes |
| CASE-05 | email | clean | ALLOW | ALLOW | 0 | — | yes |
| CASE-06 | email | injected | BLOCK | BLOCK | 100 | data_egress, local_data_access, task_expansion | yes |
| CASE-07 | rag_document | clean | ALLOW | ALLOW | 0 | — | yes |
| CASE-08 | rag_document | injected | BLOCK | BLOCK | 100 | data_egress, local_data_access, task_expansion | yes |
