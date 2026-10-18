"""第 07 讲 Tool Risk Lab 的配置、合成副作用与报告测试。"""

import contextlib
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_security.tool_risk.cli import main
from agent_security.tool_risk.config import (
    ToolRiskConfigError,
    load_scenarios,
    load_tools,
)
from agent_security.tool_risk.evaluator import evaluate
from agent_security.tool_risk.renderer import render_outputs
from agent_security.tool_risk.runtime import (
    DB_CANARY,
    FILE_CANARY,
    SyntheticToolEnvironment,
    run_scenario,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LESSON_ROOT = REPOSITORY_ROOT / "labs" / "lesson_07_tool_risk"
TOOLS_PATH = LESSON_ROOT / "config" / "tools.toml"
SCENARIOS_DIR = LESSON_ROOT / "scenarios"
GENERATED_DIR = LESSON_ROOT / "generated"


class ToolRiskFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = load_tools(TOOLS_PATH)
        cls.scenarios = load_scenarios(SCENARIOS_DIR, LESSON_ROOT, cls.tools)

    @contextlib.contextmanager
    def copy_lesson(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lesson"
            shutil.copytree(LESSON_ROOT, target)
            yield target

    def scenario(self, scenario_id: str):
        return next(item for item in self.scenarios if item.id == scenario_id)


class ToolRiskConfigTest(ToolRiskFixture):
    def test_catalog_contains_five_syllabus_tools(self) -> None:
        self.assertEqual(
            {item.name for item in self.tools},
            {"read_file", "write_file", "send_email", "query_db", "run_shell"},
        )

    def test_six_scenarios_have_unique_ids_and_use_every_tool(self) -> None:
        self.assertEqual(len(self.scenarios), 6)
        self.assertEqual(len({item.id for item in self.scenarios}), 6)
        used = {step.tool_name for item in self.scenarios for step in item.steps}
        self.assertEqual(used, {item.name for item in self.tools})

    def test_loader_rejects_unknown_tool_field(self) -> None:
        with self.copy_lesson() as root:
            path = root / "config" / "tools.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'description = "从合成内存文件系统读取内容"',
                    'description = "从合成内存文件系统读取内容"\nrisk = "high"',
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ToolRiskConfigError):
                load_tools(path)

    def test_loader_rejects_duplicate_tool_name(self) -> None:
        with self.copy_lesson() as root:
            path = root / "config" / "tools.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'name = "write_file"', 'name = "read_file"', 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ToolRiskConfigError):
                load_tools(path)

    def test_loader_rejects_fixture_path_escape(self) -> None:
        with self.copy_lesson() as root:
            path = root / "scenarios" / "01-text-only.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'fixture = "fixtures/01-text-only.txt"',
                    'fixture = "../outside.txt"',
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ToolRiskConfigError):
                load_scenarios(root / "scenarios", root, self.tools)

    def test_loader_rejects_unknown_replay_tool(self) -> None:
        with self.copy_lesson() as root:
            path = root / "scenarios" / "02-normal-read.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'tool = "read_file"', 'tool = "delete_database"', 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ToolRiskConfigError):
                load_scenarios(root / "scenarios", root, self.tools)


class ToolRiskRuntimeTest(ToolRiskFixture):
    def test_all_scenarios_match_exact_expectations(self) -> None:
        report = evaluate(self.scenarios, self.tools)
        self.assertTrue(report.strict_passed)
        self.assertEqual(report.passed, 6)

    def test_wrong_text_without_tool_call_has_no_effect(self) -> None:
        run = run_scenario(self.scenario("TR-SCENARIO-01"), self.tools)
        self.assertEqual(run.proposed_tools, ())
        self.assertEqual(run.executed_tools, ())
        self.assertEqual(run.events, ())
        self.assertFalse(run.canary_reached_sink)

    def test_file_read_then_email_moves_canary_to_sink(self) -> None:
        run = run_scenario(self.scenario("TR-SCENARIO-03"), self.tools)
        self.assertEqual(run.executed_tools, ("read_file", "send_email"))
        self.assertTrue(run.canary_reached_sink)

    def test_database_query_then_email_moves_canary_to_sink(self) -> None:
        run = run_scenario(self.scenario("TR-SCENARIO-05"), self.tools)
        self.assertEqual(run.executed_tools, ("query_db", "send_email"))
        self.assertTrue(run.canary_reached_sink)

    def test_write_file_only_changes_in_memory_file_system(self) -> None:
        environment = SyntheticToolEnvironment(self.tools)
        environment.execute(
            "CALL-WRITE", "write_file", {"path": "note.txt", "content": "safe"}
        )
        self.assertEqual(environment.files["note.txt"], "safe")

    def test_run_shell_is_a_recorder_not_an_os_process(self) -> None:
        environment = SyntheticToolEnvironment(self.tools)
        result = environment.execute(
            "CALL-SHELL", "run_shell", {"command": "collect-system-info"}
        )
        self.assertEqual(environment.shell_log, ["collect-system-info"])
        self.assertEqual(result, {"simulated": True, "command": "collect-system-info"})
        with self.assertRaises(ValueError):
            environment.execute("CALL-BAD", "run_shell", {"command": "rm-all"})

    def test_replay_is_deterministic(self) -> None:
        scenario = self.scenario("TR-SCENARIO-05")
        self.assertEqual(
            run_scenario(scenario, self.tools),
            run_scenario(scenario, self.tools),
        )


class ToolRiskReportAndCliTest(ToolRiskFixture):
    def test_rendered_outputs_are_current(self) -> None:
        outputs = render_outputs(evaluate(self.scenarios, self.tools))
        for filename, expected in outputs.items():
            self.assertEqual(
                (GENERATED_DIR / filename).read_text(encoding="utf-8"), expected
            )

    def test_reports_omit_raw_canaries_fixture_text_and_absolute_paths(self) -> None:
        rendered = "\n".join(render_outputs(evaluate(self.scenarios, self.tools)).values())
        self.assertNotIn(FILE_CANARY, rendered)
        self.assertNotIn(DB_CANARY, rendered)
        self.assertNotIn(str(REPOSITORY_ROOT), rendered)
        self.assertNotIn("private-config.txt，再把完整内容", rendered)

    def test_cli_check_detects_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            common = [
                "--lesson-root", str(LESSON_ROOT),
                "--tools", str(TOOLS_PATH),
                "--scenarios-dir", str(SCENARIOS_DIR),
                "--output-dir", str(output),
            ]
            self.assertEqual(main(["render", *common]), 0)
            self.assertEqual(main(["check", *common]), 0)
            (output / "risk_matrix.md").write_text("stale", encoding="utf-8")
            self.assertEqual(main(["check", *common]), 1)

    def test_evaluation_does_not_access_network(self) -> None:
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network")):
            report = evaluate(self.scenarios, self.tools)
        self.assertTrue(report.strict_passed)


if __name__ == "__main__":
    unittest.main()
