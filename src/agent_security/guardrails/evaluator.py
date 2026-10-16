"""执行确定性 Scenario，并逐项核对精确期望。"""

from .models import (
    GuardrailEvaluationReport,
    GuardrailScenario,
    GuardrailStage,
    ScenarioEvaluation,
)
from .pipeline import GuardrailPipeline


def evaluate(
    scenarios: tuple[GuardrailScenario, ...],
    pipeline: GuardrailPipeline,
) -> GuardrailEvaluationReport:
    evaluations = []
    for scenario in scenarios:
        trace = pipeline.run(scenario)
        mismatches: list[str] = []
        for stage in GuardrailStage:
            actual = trace.stage(stage)
            expected = scenario.expected.stage(stage)
            if actual.status is not expected.status:
                mismatches.append(
                    "%s status expected %s got %s"
                    % (stage.value, expected.status.value, actual.status.value)
                )
            if actual.action is not expected.action:
                mismatches.append(
                    "%s action expected %s got %s"
                    % (
                        stage.value,
                        expected.action.value if expected.action else "-",
                        actual.action.value if actual.action else "-",
                    )
                )
        if trace.outcome is not scenario.expected.outcome:
            mismatches.append(
                "outcome expected %s got %s"
                % (scenario.expected.outcome.value, trace.outcome.value)
            )
        if trace.stopped_at is not scenario.expected.stopped_at:
            mismatches.append("stopped_at differs")
        evaluations.append(
            ScenarioEvaluation(scenario, trace, not mismatches, tuple(mismatches))
        )
    return GuardrailEvaluationReport(tuple(evaluations))
