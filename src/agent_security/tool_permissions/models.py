"""第 08 讲 Tool Permission System 的不可变领域对象。"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from agent_security.models import ToolCall


class ToolCapability(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    NETWORK = "NETWORK"
    PAYMENT = "PAYMENT"
    ADMIN = "ADMIN"


class PermissionOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class CheckStatus(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class ToolManifest:
    name: str
    description: str
    capabilities: Tuple[ToolCapability, ...]
    required_arguments: Tuple[str, ...]
    optional_arguments: Tuple[str, ...]
    argument_types: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class SubjectContext:
    id: str
    display_name: str
    roles: Tuple[str, ...]


@dataclass(frozen=True)
class TaskContract:
    id: str
    display_name: str
    allowed_roles: Tuple[str, ...]
    allowed_tools: Tuple[str, ...]
    allowed_capabilities: Tuple[ToolCapability, ...]


@dataclass(frozen=True)
class PermissionPolicy:
    version: str
    check_order: Tuple[str, ...]


@dataclass(frozen=True)
class PermissionRequest:
    tool_name: str
    manifest: ToolManifest | None
    subject: SubjectContext
    task: TaskContract
    arguments_json: str
    validation_error: str | None


@dataclass(frozen=True)
class PolicyCheck:
    name: str
    status: CheckStatus
    reason_code: str


@dataclass(frozen=True)
class PermissionDecision:
    outcome: PermissionOutcome
    reason_code: str
    request: PermissionRequest
    checks: Tuple[PolicyCheck, ...]


@dataclass(frozen=True)
class PermissionScenario:
    id: str
    title: str
    subject_id: str
    task_id: str
    tool_call: ToolCall
    expected_outcome: PermissionOutcome
    expected_reason: str
    expected_delegated: bool


@dataclass(frozen=True)
class PermissionExecution:
    decision: PermissionDecision
    delegated: bool


@dataclass(frozen=True)
class PermissionRun:
    scenario: PermissionScenario
    execution: PermissionExecution
    passed: bool
    mismatches: Tuple[str, ...]


@dataclass(frozen=True)
class PermissionReport:
    tools: Tuple[ToolManifest, ...]
    runs: Tuple[PermissionRun, ...]

    @property
    def passed(self) -> int:
        return sum(item.passed for item in self.runs)

    @property
    def total(self) -> int:
        return len(self.runs)

    @property
    def strict_passed(self) -> bool:
        return self.passed == self.total
