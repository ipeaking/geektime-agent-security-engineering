# Policy Traces

## TP-SCENARIO-01

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- `capabilities_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- Decision: `ALLOW`
- Delegated: `yes`
- Expected result: `matched`

## TP-SCENARIO-02

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `UNSATISFIED` (`tool_not_allowed_by_task`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`

## TP-SCENARIO-03

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `UNSATISFIED` (`subject_role_not_allowed`)
- `tool_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`

## TP-SCENARIO-04

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- `capabilities_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- Decision: `ALLOW`
- Delegated: `yes`
- Expected result: `matched`

## TP-SCENARIO-05

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- `capabilities_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- Decision: `ALLOW`
- Delegated: `yes`
- Expected result: `matched`

## TP-SCENARIO-06

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `UNSATISFIED` (`subject_role_not_allowed`)
- `tool_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`

## TP-SCENARIO-07

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- `capabilities_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- Decision: `ALLOW`
- Delegated: `yes`
- Expected result: `matched`

## TP-SCENARIO-08

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `UNSATISFIED` (`tool_not_allowed_by_task`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`

## TP-SCENARIO-09

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- `capabilities_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- Decision: `ALLOW`
- Delegated: `yes`
- Expected result: `matched`

## TP-SCENARIO-10

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `UNSATISFIED` (`tool_not_allowed_by_task`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`

## TP-SCENARIO-11

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `SATISFIED` (`check_satisfied`)
- `tool_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- `capabilities_allowed_by_task`: `SATISFIED` (`check_satisfied`)
- Decision: `ALLOW`
- Delegated: `yes`
- Expected result: `matched`

## TP-SCENARIO-12

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `SATISFIED` (`check_satisfied`)
- `subject_role_allowed`: `UNSATISFIED` (`subject_role_not_allowed`)
- `tool_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`

## TP-SCENARIO-13

- `request_valid`: `SATISFIED` (`check_satisfied`)
- `tool_registered`: `UNSATISFIED` (`tool_not_registered`)
- `subject_role_allowed`: `NOT_RUN` (`earlier_check_denied`)
- `tool_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`

## TP-SCENARIO-14

- `request_valid`: `UNSATISFIED` (`argument_type_mismatch`)
- `tool_registered`: `NOT_RUN` (`earlier_check_denied`)
- `subject_role_allowed`: `NOT_RUN` (`earlier_check_denied`)
- `tool_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- `capabilities_allowed_by_task`: `NOT_RUN` (`earlier_check_denied`)
- Decision: `DENY`
- Delegated: `no`
- Expected result: `matched`
