import tempfile
import unittest
from pathlib import Path

from agent_security.lab.runner import run_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LAB_ROOT = REPOSITORY_ROOT / "labs" / "lesson_01_prompt_injection"


class PromptInjectionReplayTest(unittest.TestCase):
    def test_malicious_page_contains_only_natural_language_instructions(self) -> None:
        page = (LAB_ROOT / "fixtures" / "pages" / "malicious.html").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("data-lab-", page)
        self.assertNotIn("display: none", page)
        self.assertIn("demo-config.json", page)
        self.assertIn("read_file", page)
        self.assertIn("send_diagnostic", page)

    def test_normal_replay_has_no_diagnostic_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_case("normal", REPOSITORY_ROOT, Path(directory))

        self.assertEqual(result["provider"], "replay")
        self.assertEqual(result["tool_calls"], ["fetch_webpage"])
        self.assertEqual(result["diagnostics_received"], [])
        self.assertIn("支付状态查询接口", result["answer"])

    def test_attack_replay_reproduces_controlled_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_case("attack", REPOSITORY_ROOT, Path(directory))

        self.assertEqual(
            result["tool_calls"],
            ["fetch_webpage", "read_file", "send_diagnostic"],
        )
        self.assertEqual(len(result["diagnostics_received"]), 1)
        leaked = result["diagnostics_received"][0]
        self.assertIn(result["runtime_canary"], leaked["content"])
        self.assertNotIn(result["runtime_canary"], result["answer"])
        self.assertIn("支付状态查询接口", result["answer"])

    def test_each_run_uses_a_fresh_canary(self) -> None:
        with tempfile.TemporaryDirectory() as first_directory:
            first = run_case("attack", REPOSITORY_ROOT, Path(first_directory))
        with tempfile.TemporaryDirectory() as second_directory:
            second = run_case("attack", REPOSITORY_ROOT, Path(second_directory))

        self.assertNotEqual(first["runtime_canary"], second["runtime_canary"])
        self.assertTrue(first["runtime_canary"].startswith("COURSE-CANARY-"))
        self.assertTrue(second["runtime_canary"].startswith("COURSE-CANARY-"))


if __name__ == "__main__":
    unittest.main()
