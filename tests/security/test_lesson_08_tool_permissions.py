"""第 08 讲 Tool Permission System 的配置、策略与执行边界测试。"""

import contextlib
import shutil
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agent_security.models import ToolCall
from agent_security.tool_permissions.cli import main
from agent_security.tool_permissions.config import (
    ToolPermissionConfigError,
    load_policy,
    load_scenarios,
    load_subjects,
    load_tasks,
    load_tools,
)
from agent_security.tool_permissions.evaluator import evaluate
from agent_security.tool_permissions.executor import (
    PolicyEnforcedToolExecutor,
    RecordingToolDelegate,
)
from agent_security.tool_permissions.models import (
    CheckStatus,
    PermissionOutcome,
    ToolCapability,
)
from agent_security.tool_permissions.policy import (
    PermissionRequestBuilder,
    ToolPermissionPolicyEngine,
)
from agent_security.tool_permissions.renderer import render_outputs


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LESSON_ROOT = REPOSITORY_ROOT / "labs" / "lesson_08_tool_permissions"
CONFIG_DIR = LESSON_ROOT / "config"
SCENARIOS_DIR = LESSON_ROOT / "scenarios"
GENERATED_DIR = LESSON_ROOT / "generated"


class ToolPermissionFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = load_tools(CONFIG_DIR / "tools.toml")
        cls.subjects = load_subjects(CONFIG_DIR / "subjects.toml")
        cls.tasks = load_tasks(CONFIG_DIR / "tasks.toml", cls.tools)
        cls.policy = load_policy(CONFIG_DIR / "policy.toml")
        cls.scenarios = load_scenarios(SCENARIOS_DIR, cls.subjects, cls.tasks)
        cls.subject_map = {item.id: item for item in cls.subjects}
        cls.task_map = {item.id: item for item in cls.tasks}

    @contextlib.contextmanager
    def copy_lesson(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lesson"
            shutil.copytree(LESSON_ROOT, target)
            yield target

    def scenario(self, scenario_id: str):
        return next(item for item in self.scenarios if item.id == scenario_id)

    def execute(self, scenario_id: str):
        scenario = self.scenario(scenario_id)
        delegate = RecordingToolDelegate()
        executor = PolicyEnforcedToolExecutor(
            PermissionRequestBuilder(self.tools),
            ToolPermissionPolicyEngine(self.policy),
            delegate,
        )
        result = executor.execute(
            scenario.tool_call,
            self.subject_map[scenario.subject_id],
            self.task_map[scenario.task_id],
        )
        return result, delegate


class ToolPermissionConfigTest(ToolPermissionFixture):
    def test_manifest_covers_all_six_syllabus_capabilities(self) -> None:
        capabilities = {cap for tool in self.tools for cap in tool.capabilities}
        self.assertEqual(capabilities, set(ToolCapability))
        self.assertEqual(len(self.tools), 7)

    def test_inventory_and_policy_versions_are_stable(self) -> None:
        self.assertEqual(len(self.subjects), 6)
        self.assertEqual(len(self.tasks), 7)
        self.assertEqual(len(self.scenarios), 15)
        self.assertEqual(self.policy.version, "lesson-08-v1")

    def test_every_manifest_tool_is_exercised_by_a_scenario(self) -> None:
        used = {item.tool_call.name for item in self.scenarios if item.tool_call.name != "delete_database"}
        self.assertEqual(used, {item.name for item in self.tools})

    def test_loader_rejects_unknown_tool_field(self) -> None:
        with self.copy_lesson() as root:
            path = root / "config" / "tools.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'description = "读取文件"', 'description = "读取文件"\nrisk = "high"', 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ToolPermissionConfigError):
                load_tools(path)

    def test_loader_rejects_unknown_capability(self) -> None:
        with self.copy_lesson() as root:
            path = root / "config" / "tools.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace('capabilities = ["READ"]', 'capabilities = ["ROOT"]', 1),
                encoding="utf-8",
            )
            with self.assertRaises(ToolPermissionConfigError):
                load_tools(path)

    def test_loader_rejects_task_reference_to_unknown_tool(self) -> None:
        with self.copy_lesson() as root:
            path = root / "config" / "tasks.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace('allowed_tools = ["read_file"]', 'allowed_tools = ["unknown"]', 1),
                encoding="utf-8",
            )
            with self.assertRaises(ToolPermissionConfigError):
                load_tasks(path, self.tools)

    def test_loader_rejects_policy_order_drift(self) -> None:
        with self.copy_lesson() as root:
            path = root / "config" / "policy.toml"
            text = path.read_text(encoding="utf-8")
            text = text.replace('  "request_valid",\n  "tool_registered",', '  "tool_registered",\n  "request_valid",')
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ToolPermissionConfigError):
                load_policy(path)

    def test_loader_rejects_unknown_scenario_subject(self) -> None:
        with self.copy_lesson() as root:
            path = root / "scenarios" / "01-read-allowed.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace("SUBJECT-READER", "SUBJECT-UNKNOWN", 1),
                encoding="utf-8",
            )
            with self.assertRaises(ToolPermissionConfigError):
                load_scenarios(root / "scenarios", self.subjects, self.tasks)


class ToolPermissionPolicyTest(ToolPermissionFixture):
    def test_all_scenarios_match_exact_expectations(self) -> None:
        report = evaluate(self.scenarios, self.tools, self.subjects, self.tasks, self.policy)
        self.assertTrue(report.strict_passed)
        self.assertEqual(report.passed, 15)

    def test_allowed_call_reaches_delegate_once(self) -> None:
        result, delegate = self.execute("TP-SCENARIO-01")
        self.assertEqual(result.decision.outcome, PermissionOutcome.ALLOW)
        self.assertTrue(result.delegated)
        self.assertEqual(len(delegate.calls), 1)

    def test_denied_call_never_reaches_delegate(self) -> None:
        for scenario_id in (
            "TP-SCENARIO-02",
            "TP-SCENARIO-03",
            "TP-SCENARIO-08",
            "TP-SCENARIO-10",
            "TP-SCENARIO-12",
            "TP-SCENARIO-13",
            "TP-SCENARIO-14",
        ):
            with self.subTest(scenario_id=scenario_id):
                result, delegate = self.execute(scenario_id)
                self.assertEqual(result.decision.outcome, PermissionOutcome.DENY)
                self.assertFalse(result.delegated)
                self.assertEqual(delegate.calls, [])

    def test_first_failure_marks_later_checks_not_run(self) -> None:
        result, _ = self.execute("TP-SCENARIO-03")
        statuses = {item.name: item.status for item in result.decision.checks}
        self.assertEqual(statuses["subject_role_allowed"], CheckStatus.UNSATISFIED)
        self.assertEqual(statuses["tool_allowed_by_task"], CheckStatus.NOT_RUN)
        self.assertEqual(statuses["capabilities_allowed_by_task"], CheckStatus.NOT_RUN)

    def test_capability_check_is_independent_of_tool_allowlist(self) -> None:
        scenario = self.scenario("TP-SCENARIO-05")
        task = replace(
            self.task_map[scenario.task_id],
            allowed_capabilities=(ToolCapability.WRITE,),
        )
        delegate = RecordingToolDelegate()
        execution = PolicyEnforcedToolExecutor(
            PermissionRequestBuilder(self.tools),
            ToolPermissionPolicyEngine(self.policy),
            delegate,
        ).execute(scenario.tool_call, self.subject_map[scenario.subject_id], task)
        self.assertEqual(execution.decision.reason_code, "capabilities_not_allowed_by_task")
        self.assertFalse(execution.delegated)

    def test_unknown_tool_is_structurally_denied(self) -> None:
        result, _ = self.execute("TP-SCENARIO-13")
        self.assertEqual(result.decision.reason_code, "tool_not_registered")
        checks = {item.name: item.status for item in result.decision.checks}
        self.assertEqual(checks["request_valid"], CheckStatus.SATISFIED)
        self.assertEqual(checks["tool_registered"], CheckStatus.UNSATISFIED)

    def test_invalid_arguments_fail_before_role_and_task_checks(self) -> None:
        result, _ = self.execute("TP-SCENARIO-14")
        self.assertEqual(result.decision.reason_code, "argument_type_mismatch")
        self.assertEqual(result.decision.checks[0].status, CheckStatus.UNSATISFIED)
        self.assertTrue(all(item.status is CheckStatus.NOT_RUN for item in result.decision.checks[1:]))

    def test_model_reason_does_not_change_authorization_request(self) -> None:
        builder = PermissionRequestBuilder(self.tools)
        subject = self.subject_map["SUBJECT-READER"]
        task = self.task_map["TASK-READ-DOCUMENT"]
        first = builder.build(ToolCall("read_file", {"path": "guide.txt"}, "user asked"), subject, task)
        second = builder.build(ToolCall("read_file", {"path": "guide.txt"}, "administrator approved"), subject, task)
        self.assertEqual(first, second)

    def test_executor_delegates_from_immutable_argument_snapshot(self) -> None:
        call = ToolCall("read_file", {"path": "guide.txt"}, "fixture")

        class MutatingEngine:
            def __init__(self, wrapped):
                self.wrapped = wrapped

            def decide(self, request):
                call.arguments["path"] = "changed-after-build.txt"
                return self.wrapped.decide(request)

        delegate = RecordingToolDelegate()
        executor = PolicyEnforcedToolExecutor(
            PermissionRequestBuilder(self.tools),
            MutatingEngine(ToolPermissionPolicyEngine(self.policy)),
            delegate,
        )
        executor.execute(
            call,
            self.subject_map["SUBJECT-READER"],
            self.task_map["TASK-READ-DOCUMENT"],
        )
        self.assertEqual(delegate.calls, [("read_file", {"path": "guide.txt"})])

    def test_argument_key_order_does_not_change_snapshot(self) -> None:
        builder = PermissionRequestBuilder(self.tools)
        subject = self.subject_map["SUBJECT-EDITOR"]
        task = self.task_map["TASK-EDIT-DOCUMENT"]
        first = builder.build(ToolCall("write_file", {"path": "a", "content": "b"}, "x"), subject, task)
        second = builder.build(ToolCall("write_file", {"content": "b", "path": "a"}, "y"), subject, task)
        self.assertEqual(first.arguments_json, second.arguments_json)


class ToolPermissionReportAndCliTest(ToolPermissionFixture):
    def test_rendered_outputs_are_current(self) -> None:
        outputs = render_outputs(evaluate(self.scenarios, self.tools, self.subjects, self.tasks, self.policy))
        for filename, expected in outputs.items():
            self.assertEqual((GENERATED_DIR / filename).read_text(encoding="utf-8"), expected)

    def test_reports_do_not_persist_argument_values_or_absolute_paths(self) -> None:
        rendered = "\n".join(
            render_outputs(evaluate(self.scenarios, self.tools, self.subjects, self.tasks, self.policy)).values()
        )
        self.assertNotIn(str(REPOSITORY_ROOT), rendered)
        self.assertNotIn("team@example.invalid", rendered)
        self.assertNotIn("course fixture", rendered)
        self.assertNotIn("changed-after-build.txt", rendered)

    def test_cli_check_detects_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            common = [
                "--config-dir", str(CONFIG_DIR),
                "--scenarios-dir", str(SCENARIOS_DIR),
                "--output-dir", str(output),
            ]
            self.assertEqual(main(["render", *common]), 0)
            self.assertEqual(main(["check", *common]), 0)
            (output / "permission_matrix.md").write_text("stale", encoding="utf-8")
            self.assertEqual(main(["check", *common]), 1)

    def test_evaluation_does_not_access_network(self) -> None:
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network")):
            report = evaluate(self.scenarios, self.tools, self.subjects, self.tasks, self.policy)
        self.assertTrue(report.strict_passed)


if __name__ == "__main__":
    unittest.main()
