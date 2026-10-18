"""第 07 讲 Tool Risk Lab 的不可变领域对象。"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class ToolEffect(str, Enum):
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    EMAIL_SENT = "EMAIL_SENT"
    DB_QUERY = "DB_QUERY"
    SHELL_COMMAND = "SHELL_COMMAND"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    effect: ToolEffect
    description: str


@dataclass(frozen=True)
class ReplayStep:
    call_id: str
    tool_name: str
    arguments: Tuple[Tuple[str, object], ...]


@dataclass(frozen=True)
class ToolRiskExpectation:
    proposed_tools: Tuple[str, ...]
    executed_tools: Tuple[str, ...]
    effects: Tuple[ToolEffect, ...]
    canary_reached_sink: bool


@dataclass(frozen=True)
class ToolRiskScenario:
    id: str
    title: str
    fixture_ref: str
    fixture_sha256: str
    final_text: str
    steps: Tuple[ReplayStep, ...]
    expected: ToolRiskExpectation


@dataclass(frozen=True)
class ToolEvent:
    call_id: str
    tool_name: str
    effect: ToolEffect
    evidence: str


@dataclass(frozen=True)
class ToolRiskRun:
    scenario: ToolRiskScenario
    proposed_tools: Tuple[str, ...]
    executed_tools: Tuple[str, ...]
    events: Tuple[ToolEvent, ...]
    canary_reached_sink: bool
    passed: bool
    mismatches: Tuple[str, ...]


@dataclass(frozen=True)
class ToolRiskReport:
    tools: Tuple[ToolSpec, ...]
    runs: Tuple[ToolRiskRun, ...]

    @property
    def passed(self) -> int:
        return sum(item.passed for item in self.runs)

    @property
    def total(self) -> int:
        return len(self.runs)

    @property
    def strict_passed(self) -> bool:
        return self.passed == self.total
