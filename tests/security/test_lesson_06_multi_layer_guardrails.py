"""第 06 讲多层 Guardrails 的配置、短路、Trace 与回归测试。"""

import contextlib
import shutil
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agent_security.guardrails.cli import main
from agent_security.guardrails.config import (
    GuardrailConfigError,
    load_guardrail_policy,
    load_scenarios,
)
from agent_security.guardrails.context_guard import ContextGuard
from agent_security.guardrails.evaluator import evaluate
from agent_security.guardrails.models import (
    GuardrailAction,
    GuardrailStage,
    OutputMode,
    PipelineOutcome,
    ReplayPlan,
    SegmentInspection,
    StageStatus,
)
from agent_security.guardrails.output_guard import OutputGuard
from agent_security.guardrails.pipeline import GuardrailPipeline
from agent_security.guardrails.renderer import render_outputs
from agent_security.prompt_firewall.config import load_policy, load_rules
from agent_security.prompt_firewall.firewall import PromptFirewall


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LESSON_ROOT = REPOSITORY_ROOT / "labs" / "lesson_06_multi_layer_guardrails"
SCENARIOS_DIR = LESSON_ROOT / "scenarios"
FIREWALL_ROOT = REPOSITORY_ROOT / "labs" / "lesson_05_prompt_firewall"
GENERATED_DIR = LESSON_ROOT / "generated"
GUARDRAIL_POLICY_PATH = LESSON_ROOT / "config" / "guardrails.toml"


class GuardrailFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guardrail_policy = load_guardrail_policy(GUARDRAIL_POLICY_PATH)
        cls.scenarios = load_scenarios(
            SCENARIOS_DIR,
            LESSON_ROOT,
            FIREWALL_ROOT,
            cls.guardrail_policy,
        )
        rules = load_rules(FIREWALL_ROOT / "config" / "rules.toml")
        policy = load_policy(FIREWALL_ROOT / "config" / "policy.toml")
        cls.pipeline = GuardrailPipeline(
            PromptFirewall(rules, policy),
            cls.guardrail_policy,
        )

    @contextlib.contextmanager
    def copy_lesson(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lesson"
            shutil.copytree(LESSON_ROOT, target)
            yield target


class GuardrailConfigTest(GuardrailFixture):
    def test_eight_scenarios_have_unique_ids(self) -> None:
        self.assertEqual(len(self.scenarios), 8)
        self.assertEqual(len({item.id for item in self.scenarios}), 8)
        self.assertEqual(self.guardrail_policy.version, "lesson-06-v1")
        self.assertEqual(len(self.guardrail_policy.cross_segment_combinations), 4)

    def test_loader_rejects_duplicate_scenario_id(self) -> None:
        with self.copy_lesson() as root:
            shutil.copy(root / "scenarios" / "01_clean_summary.toml", root / "scenarios" / "09_duplicate.toml")
            with self.assertRaises(GuardrailConfigError):
                load_scenarios(root / "scenarios", root, FIREWALL_ROOT, self.guardrail_policy)

    def test_loader_rejects_fixture_path_escape(self) -> None:
        with self.copy_lesson() as root:
            path = root / "scenarios" / "07_source_label_spoofing.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'fixture = "fixtures/content/source-spoof.txt"',
                    'fixture = "../outside.txt"',
                ),
                encoding="utf-8",
            )
            with self.assertRaises(GuardrailConfigError):
                load_scenarios(root / "scenarios", root, FIREWALL_ROOT, self.guardrail_policy)

    def test_loader_rejects_unknown_tool(self) -> None:
        with self.copy_lesson() as root:
            path = root / "scenarios" / "01_clean_summary.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace('"load_content"', '"delete_all"', 1),
                encoding="utf-8",
            )
            with self.assertRaises(GuardrailConfigError):
                load_scenarios(root / "scenarios", root, FIREWALL_ROOT, self.guardrail_policy)

    def test_loader_rejects_stage_execution_after_expected_block(self) -> None:
        with self.copy_lesson() as root:
            path = root / "scenarios" / "02_explicit_attack.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'status = "NOT_RUN"',
                    'status = "EXECUTED"\naction = "PASS"',
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(GuardrailConfigError):
                load_scenarios(root / "scenarios", root, FIREWALL_ROOT, self.guardrail_policy)


class GuardrailPipelineTest(GuardrailFixture):
    def _trace(self, scenario_id: str):
        scenario = next(item for item in self.scenarios if item.id == scenario_id)
        return self.pipeline.run(scenario)

    def test_all_scenarios_match_exact_expectations(self) -> None:
        report = evaluate(self.scenarios, self.pipeline)
        self.assertTrue(report.strict_passed)
        self.assertEqual(report.passed, 8)

    def test_input_block_short_circuits_later_stages(self) -> None:
        trace = self._trace("GR-SCENARIO-02")
        self.assertEqual(trace.stopped_at, GuardrailStage.INPUT)
        for stage in (GuardrailStage.CONTEXT, GuardrailStage.TOOL_PROPOSAL, GuardrailStage.OUTPUT):
            self.assertEqual(trace.stage(stage).status, StageStatus.NOT_RUN)

    def test_context_block_short_circuits_tool_and_output(self) -> None:
        trace = self._trace("GR-SCENARIO-06")
        self.assertEqual(trace.stopped_at, GuardrailStage.CONTEXT)
        self.assertEqual(trace.stage(GuardrailStage.TOOL_PROPOSAL).status, StageStatus.NOT_RUN)
        self.assertEqual(trace.stage(GuardrailStage.OUTPUT).status, StageStatus.NOT_RUN)

    def test_tool_block_short_circuits_output(self) -> None:
        trace = self._trace("GR-SCENARIO-03")
        self.assertEqual(trace.stopped_at, GuardrailStage.TOOL_PROPOSAL)
        self.assertEqual(
            trace.stage(GuardrailStage.TOOL_PROPOSAL).events[0].reason_code,
            "unauthorized_sensitive_tool_with_untrusted_context",
        )
        self.assertEqual(trace.stage(GuardrailStage.OUTPUT).status, StageStatus.NOT_RUN)

    def test_clean_scenario_executes_all_stages(self) -> None:
        trace = self._trace("GR-SCENARIO-01")
        self.assertEqual(trace.outcome, PipelineOutcome.COMPLETED)
        self.assertTrue(all(item.status is StageStatus.EXECUTED for item in trace.stages))
        self.assertTrue(all(item.action is GuardrailAction.PASS for item in trace.stages))

    def test_trace_order_and_content_are_deterministic(self) -> None:
        first = self._trace("GR-SCENARIO-07")
        second = self._trace("GR-SCENARIO-07")
        self.assertEqual(first, second)
        self.assertEqual(tuple(item.stage for item in first.stages), tuple(GuardrailStage))

    def test_three_lesson05_bypasses_still_pass_input_guard(self) -> None:
        for scenario_id in ("GR-SCENARIO-03", "GR-SCENARIO-04", "GR-SCENARIO-05"):
            with self.subTest(scenario_id=scenario_id):
                self.assertEqual(
                    self._trace(scenario_id).stage(GuardrailStage.INPUT).action,
                    GuardrailAction.PASS,
                )

    def test_replay_tool_call_has_stable_id_but_trace_does_not_persist_it(self) -> None:
        scenario = next(item for item in self.scenarios if item.id == "GR-SCENARIO-03")
        self.assertEqual(scenario.replay.tool_call.call_id, "GR-SCENARIO-03-CALL-001")
        rendered = render_outputs(evaluate((scenario,), self.pipeline))["evaluation_results.json"]
        self.assertNotIn("call_id", rendered)
        self.assertNotIn("demo-config.json", rendered)

    def test_no_tool_proposal_is_not_applicable_not_pass(self) -> None:
        scenario = next(item for item in self.scenarios if item.id == "GR-SCENARIO-01")
        changed = replace(scenario, replay=ReplayPlan(None, scenario.replay.output_text, ()))
        trace = self.pipeline.run(changed)
        record = trace.stage(GuardrailStage.TOOL_PROPOSAL)
        self.assertEqual(record.status, StageStatus.NOT_APPLICABLE)
        self.assertIsNone(record.action)


class ContextAndOutputGuardTest(GuardrailFixture):
    def test_context_guard_retains_program_metadata_over_spoofed_labels(self) -> None:
        scenario = next(item for item in self.scenarios if item.id == "GR-SCENARIO-07")
        trace = self.pipeline.run(scenario)
        event = trace.stage(GuardrailStage.CONTEXT).events[0]
        self.assertEqual(event.reason_code, "source_label_spoofing")
        self.assertEqual(dict(event.details)["program_metadata_retained"], "true")
        self.assertEqual(scenario.segments[0].source, "webpage")
        self.assertEqual(scenario.segments[0].trust, "untrusted")

    def test_context_guard_rejects_content_hash_mismatch(self) -> None:
        scenario = next(item for item in self.scenarios if item.id == "GR-SCENARIO-01")
        inspection = self.pipeline._inspect_segment(scenario.segments[0])
        broken = replace(inspection.segment, content_sha256="0" * 64)
        event = ContextGuard(self.guardrail_policy).inspect(
            (replace(inspection, segment=broken),)
        )
        self.assertEqual(event.action, GuardrailAction.BLOCK)
        self.assertEqual(event.reason_code, "context_metadata_integrity_failed")

    def test_cross_segment_chain_uses_prior_structured_findings(self) -> None:
        trace = self.pipeline.run(next(item for item in self.scenarios if item.id == "GR-SCENARIO-06"))
        event = trace.stage(GuardrailStage.CONTEXT).events[0]
        self.assertEqual(event.reason_code, "cross_segment_risk_chain")
        self.assertEqual(set(event.evidence), {"local_data_access", "data_egress"})

    def test_output_guard_blocks_without_persisting_canary_as_evidence(self) -> None:
        trace = self.pipeline.run(next(item for item in self.scenarios if item.id == "GR-SCENARIO-08"))
        event = trace.stage(GuardrailStage.OUTPUT).events[0]
        self.assertEqual(event.action, GuardrailAction.BLOCK)
        self.assertEqual(event.evidence, ("[SYNTHETIC_CANARY]",))
        self.assertIsNone(trace.output_text)

    def test_output_guard_redact_mode_replaces_exact_canary(self) -> None:
        event, output = OutputGuard(self.guardrail_policy).inspect(
            "before COURSE-CANARY-TEST after",
            ("COURSE-CANARY-TEST",),
            OutputMode.REDACT,
        )
        self.assertEqual(event.action, GuardrailAction.REDACT)
        self.assertEqual(
            output,
            "before %s after" % self.guardrail_policy.redaction_token,
        )


class GuardrailReportAndCliTest(GuardrailFixture):
    def test_rendered_outputs_are_current(self) -> None:
        outputs = render_outputs(evaluate(self.scenarios, self.pipeline))
        for filename, expected in outputs.items():
            self.assertEqual((GENERATED_DIR / filename).read_text(encoding="utf-8"), expected)

    def test_reports_do_not_contain_absolute_paths_or_raw_canary(self) -> None:
        outputs = render_outputs(evaluate(self.scenarios, self.pipeline))
        combined = "\n".join(outputs.values())
        self.assertNotIn(str(REPOSITORY_ROOT), combined)
        self.assertNotIn("COURSE-CANARY-LESSON-06", combined)

    def test_cli_check_and_evaluate_succeed(self) -> None:
        self.assertEqual(main(["check"]), 0)
        self.assertEqual(main(["evaluate", "--strict"]), 0)

    def test_evaluation_never_accesses_network(self) -> None:
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network called")):
            report = evaluate(self.scenarios, self.pipeline)
        self.assertTrue(report.strict_passed)


if __name__ == "__main__":
    unittest.main()
