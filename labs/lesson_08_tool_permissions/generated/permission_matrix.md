# Tool Permission Matrix

| Scenario | Subject | Task | Tool | Decision | Reason | Delegated |
| --- | --- | --- | --- | --- | --- | --- |
| TP-SCENARIO-01 | SUBJECT-READER | TASK-READ-DOCUMENT | read_file | ALLOW | all_required_checks_satisfied | yes |
| TP-SCENARIO-02 | SUBJECT-READER | TASK-READ-DOCUMENT | write_file | DENY | tool_not_allowed_by_task | no |
| TP-SCENARIO-03 | SUBJECT-READER | TASK-EDIT-DOCUMENT | write_file | DENY | subject_role_not_allowed | no |
| TP-SCENARIO-04 | SUBJECT-EDITOR | TASK-EDIT-DOCUMENT | write_file | ALLOW | all_required_checks_satisfied | yes |
| TP-SCENARIO-05 | SUBJECT-COMMUNICATOR | TASK-SEND-UPDATE | send_email | ALLOW | all_required_checks_satisfied | yes |
| TP-SCENARIO-06 | SUBJECT-READER | TASK-SEND-UPDATE | send_email | DENY | subject_role_not_allowed | no |
| TP-SCENARIO-07 | SUBJECT-OPERATOR | TASK-MAINTENANCE | run_shell | ALLOW | all_required_checks_satisfied | yes |
| TP-SCENARIO-08 | SUBJECT-READER | TASK-READ-DOCUMENT | run_shell | DENY | tool_not_allowed_by_task | no |
| TP-SCENARIO-09 | SUBJECT-BILLING | TASK-BILLING | charge_payment | ALLOW | all_required_checks_satisfied | yes |
| TP-SCENARIO-10 | SUBJECT-COMMUNICATOR | TASK-SEND-UPDATE | charge_payment | DENY | tool_not_allowed_by_task | no |
| TP-SCENARIO-11 | SUBJECT-ADMIN | TASK-USER-ADMIN | manage_users | ALLOW | all_required_checks_satisfied | yes |
| TP-SCENARIO-12 | SUBJECT-OPERATOR | TASK-USER-ADMIN | manage_users | DENY | subject_role_not_allowed | no |
| TP-SCENARIO-13 | SUBJECT-OPERATOR | TASK-MAINTENANCE | delete_database | DENY | tool_not_registered | no |
| TP-SCENARIO-14 | SUBJECT-READER | TASK-READ-DOCUMENT | read_file | DENY | argument_type_mismatch | no |
| TP-SCENARIO-15 | SUBJECT-READER | TASK-DATA-QUERY | query_db | ALLOW | all_required_checks_satisfied | yes |

通过：15/15。
