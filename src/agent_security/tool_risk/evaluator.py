"""评估第 07 讲固定 ToolCall Replay 与合成副作用。"""

from .models import ToolRiskReport, ToolRiskScenario, ToolSpec
from .runtime import run_scenario


def evaluate(
    scenarios: tuple[ToolRiskScenario, ...],
    tools: tuple[ToolSpec, ...],
) -> ToolRiskReport:
    return ToolRiskReport(
        tools=tools,
        runs=tuple(run_scenario(item, tools) for item in scenarios),
    )
