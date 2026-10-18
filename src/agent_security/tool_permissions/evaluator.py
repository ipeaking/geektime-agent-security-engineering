"""执行第 08 讲固定授权 Scenario。"""

from .executor import PolicyEnforcedToolExecutor, RecordingToolDelegate
from .models import (
    PermissionPolicy,
    PermissionReport,
    PermissionRun,
    PermissionScenario,
    SubjectContext,
    TaskContract,
    ToolManifest,
)
from .policy import PermissionRequestBuilder, ToolPermissionPolicyEngine


def evaluate(
    scenarios: tuple[PermissionScenario, ...],
    tools: tuple[ToolManifest, ...],
    subjects: tuple[SubjectContext, ...],
    tasks: tuple[TaskContract, ...],
    policy: PermissionPolicy,
) -> PermissionReport:
    subject_map = {item.id: item for item in subjects}
    task_map = {item.id: item for item in tasks}
    runs: list[PermissionRun] = []
    for scenario in scenarios:
        delegate = RecordingToolDelegate()
        executor = PolicyEnforcedToolExecutor(
            PermissionRequestBuilder(tools),
            ToolPermissionPolicyEngine(policy),
            delegate,
        )
        execution = executor.execute(
            scenario.tool_call,
            subject_map[scenario.subject_id],
            task_map[scenario.task_id],
        )
        mismatches: list[str] = []
        if execution.decision.outcome is not scenario.expected_outcome:
            mismatches.append("outcome mismatch")
        if execution.decision.reason_code != scenario.expected_reason:
            mismatches.append("reason mismatch")
        if execution.delegated != scenario.expected_delegated:
            mismatches.append("delegated mismatch")
        if len(delegate.calls) != (1 if execution.delegated else 0):
            mismatches.append("delegate call count mismatch")
        runs.append(PermissionRun(scenario, execution, not mismatches, tuple(mismatches)))
    return PermissionReport(tools, tuple(runs))
