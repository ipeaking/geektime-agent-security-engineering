"""第 02 讲可执行威胁模型的回归测试。"""

import unittest
from dataclasses import replace
from pathlib import Path

from agent_security.threat_model import (
    load_threat_model,
    render_report,
    validate_threat_model,
)


class ThreatModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[2]
        cls.model_dir = (
            cls.repository_root / "labs" / "lesson_02_threat_model" / "model"
        )
        cls.model = load_threat_model(cls.model_dir)

    def test_model_loads_expected_inventory(self) -> None:
        self.assertEqual(self.model.schema_version, "1.0")
        self.assertEqual(len(self.model.components), 11)
        self.assertEqual(len(self.model.data_flows), 16)
        self.assertEqual(len(self.model.threats), 5)

    def test_model_is_valid_against_current_source_tree(self) -> None:
        self.assertEqual(
            validate_threat_model(self.model, self.repository_root),
            [],
        )

    def test_prompt_injection_threat_contains_complete_execution_chain(self) -> None:
        threat = self.model.get_threat("THR-001")
        self.assertIn("CMP-006", threat.affected_components)
        self.assertIn("CMP-007", threat.affected_components)
        self.assertIn("TB-004", threat.trust_boundaries)
        self.assertIn("DF-009", threat.attack_flows)
        self.assertIn("DF-011", threat.attack_flows)

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(render_report(self.model), render_report(self.model))

    def test_generated_report_is_up_to_date(self) -> None:
        report_path = (
            self.repository_root
            / "labs"
            / "lesson_02_threat_model"
            / "generated"
            / "threat_model_report.md"
        )
        self.assertEqual(
            report_path.read_text(encoding="utf-8"),
            render_report(self.model),
        )

    def test_unknown_asset_reference_is_rejected(self) -> None:
        broken_flow = replace(
            self.model.data_flows[0],
            assets=("AST-999",),
        )
        broken_model = replace(
            self.model,
            data_flows=(broken_flow,) + self.model.data_flows[1:],
        )
        codes = {
            issue.code
            for issue in validate_threat_model(broken_model, self.repository_root)
        }
        self.assertIn("TM021", codes)

    def test_duplicate_identifier_is_rejected(self) -> None:
        broken_model = replace(
            self.model,
            actors=self.model.actors + (self.model.actors[0],),
        )
        codes = {
            issue.code
            for issue in validate_threat_model(broken_model, self.repository_root)
        }
        self.assertIn("TM002", codes)

    def test_runtime_tool_drift_is_rejected(self) -> None:
        changed_tool = replace(self.model.components[4], tool_name="renamed_tool")
        broken_model = replace(
            self.model,
            components=self.model.components[:4]
            + (changed_tool,)
            + self.model.components[5:],
        )
        codes = {
            issue.code
            for issue in validate_threat_model(broken_model, self.repository_root)
        }
        self.assertIn("TM060", codes)

    def test_every_p1_threat_has_requirement_and_verification(self) -> None:
        verified_requirements = {
            requirement_id
            for verification in self.model.verifications
            for requirement_id in verification.verifies_requirements
        }
        for threat in self.model.threats:
            if threat.priority != "P1":
                continue
            requirements = {
                requirement.id
                for requirement in self.model.requirements
                if threat.id in requirement.derived_from
            }
            self.assertTrue(requirements, threat.id)
            self.assertTrue(requirements & verified_requirements, threat.id)


if __name__ == "__main__":
    unittest.main()
