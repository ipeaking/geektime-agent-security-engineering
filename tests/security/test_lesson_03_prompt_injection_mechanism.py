"""第 03 讲 Context Lab 的结构、确定性和安全边界测试。"""

import contextlib
import io
import json
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent_security.context_lab.builder import PREVIEW_LIMIT, build_context
from agent_security.context_lab.cli import main
from agent_security.context_lab.errors import CaseLoadError, LocalOriginViolation
from agent_security.context_lab.live_runtime import ContextLabRuntime
from agent_security.context_lab.loader import load_cases
from agent_security.context_lab.models import LiveObservation
from agent_security.context_lab.observation_executor import (
    LocalPageFetcher,
    ObservationExecutor,
)
from agent_security.context_lab.renderer import render_outputs
from agent_security.context_lab.reporter import build_observation_matrix
from agent_security.context_lab.validator import EXPECTED_CASE_IDS, validate_cases
from agent_security.lab.server import LocalLabServer
from agent_security.models import ToolCall


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LESSON_ROOT = REPOSITORY_ROOT / "labs" / "lesson_03_prompt_injection_mechanism"
CASES_DIR = LESSON_ROOT / "cases"
GENERATED_DIR = LESSON_ROOT / "generated"


class ContextLabCaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases(CASES_DIR)
        cls.by_id = {case.id: case for case in cls.cases}

    def test_six_cases_load_and_validate(self) -> None:
        self.assertEqual(set(self.by_id), EXPECTED_CASE_IDS)
        self.assertEqual(validate_cases(self.cases, LESSON_ROOT), [])

    def test_all_injection_cases_share_one_payload(self) -> None:
        payloads = {
            case.payload_fixture
            for case in self.cases
            if case.id != "CASE-01"
        }
        self.assertEqual(
            payloads,
            {"fixtures/payloads/injection.txt"},
        )
        self.assertIsNone(self.by_id["CASE-01"].payload_fixture)

    def test_wrapper_cases_only_change_wrapper(self) -> None:
        baseline = self.by_id["CASE-03"]
        for case_id in ("CASE-04", "CASE-05"):
            candidate = self.by_id[case_id]
            self.assertEqual(candidate.task, baseline.task)
            self.assertEqual(candidate.page_fixture, baseline.page_fixture)
            self.assertEqual(candidate.payload_fixture, baseline.payload_fixture)
            self.assertEqual(candidate.prompt_profile, baseline.prompt_profile)
            self.assertNotEqual(candidate.wrapper, baseline.wrapper)

    def test_explicit_boundary_case_only_changes_prompt(self) -> None:
        baseline = self.by_id["CASE-03"]
        candidate = self.by_id["CASE-06"]
        self.assertEqual(candidate.task, baseline.task)
        self.assertEqual(candidate.page_fixture, baseline.page_fixture)
        self.assertEqual(candidate.payload_fixture, baseline.payload_fixture)
        self.assertEqual(candidate.wrapper, baseline.wrapper)
        self.assertNotEqual(candidate.prompt_profile, baseline.prompt_profile)

    def test_loader_rejects_unknown_field(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "01_clean_web.toml"
            path.write_text(path.read_text(encoding="utf-8") + "\nextra = true\n", encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_unknown_enum(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "01_clean_web.toml"
            text = path.read_text(encoding="utf-8").replace(
                'channel = "clean_web"', 'channel = "email"'
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_unknown_wrapper(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "03_web_raw.toml"
            text = path.read_text(encoding="utf-8").replace(
                'wrapper = "none"', 'wrapper = "magic_filter"'
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_unknown_prompt_profile(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "03_web_raw.toml"
            text = path.read_text(encoding="utf-8").replace(
                'prompt_profile = "neutral"', 'prompt_profile = "perfect_guard"'
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_missing_required_field(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "03_web_raw.toml"
            text = path.read_text(encoding="utf-8").replace(
                'wrapper = "none"\n', ""
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_duplicate_case_id(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "02_inline_quoted_content.toml"
            text = path.read_text(encoding="utf-8").replace(
                'id = "CASE-02"', 'id = "CASE-01"'
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_path_escape(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "01_clean_web.toml"
            text = path.read_text(encoding="utf-8").replace(
                'page_fixture = "fixtures/pages/clean.html"',
                'page_fixture = "../outside.html"',
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_missing_fixture(self) -> None:
        with self._copy_lesson() as root:
            (root / "fixtures" / "pages" / "clean.html").unlink()
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_validator_rejects_payload_in_clean_page(self) -> None:
        with self._copy_lesson() as root:
            clean = root / "fixtures" / "pages" / "clean.html"
            payload = (root / "fixtures" / "payloads" / "injection.txt").read_text(
                encoding="utf-8"
            )
            clean.write_text(clean.read_text(encoding="utf-8") + payload, encoding="utf-8")
            issues = validate_cases(load_cases(root / "cases"), root)
        self.assertIn("CL005", {issue.code for issue in issues})

    def test_context_trace_marks_source_trust_and_role(self) -> None:
        built = build_context(self.by_id["CASE-03"], LESSON_ROOT)
        system, user, webpage = built.trace.items
        self.assertEqual((system.source, system.trust, system.intended_role), ("system", "trusted", "instruction"))
        self.assertEqual((user.source, user.trust, user.intended_role), ("user", "user_controlled", "instruction"))
        self.assertEqual((webpage.source, webpage.trust, webpage.intended_role), ("webpage", "untrusted", "data"))

    def test_inline_material_is_data_not_system_instruction(self) -> None:
        built = build_context(self.by_id["CASE-02"], LESSON_ROOT)
        embedded = built.trace.items[-1]
        self.assertEqual(embedded.source, "user_embedded_content")
        self.assertEqual(embedded.intended_role, "data")
        self.assertEqual(embedded.transport, "user_message")
        self.assertIsNone(built.page_content)

    def test_context_trace_is_bounded_and_deterministic(self) -> None:
        first = build_context(self.by_id["CASE-05"], LESSON_ROOT).trace
        second = build_context(self.by_id["CASE-05"], LESSON_ROOT).trace
        self.assertEqual(first, second)
        for item in first.items:
            self.assertEqual(len(item.content_sha256), 64)
            self.assertLessEqual(len(item.content_preview), PREVIEW_LIMIT)

    def test_wrappers_preserve_the_complete_payload(self) -> None:
        payload = (LESSON_ROOT / "fixtures" / "payloads" / "injection.txt").read_text(
            encoding="utf-8"
        )
        for case_id in ("CASE-03", "CASE-04", "CASE-05", "CASE-06"):
            page = build_context(self.by_id[case_id], LESSON_ROOT).page_content
            self.assertIsNotNone(page)
            self.assertIn(payload, page)

    @contextlib.contextmanager
    def _copy_lesson(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lesson"
            shutil.copytree(LESSON_ROOT, target)
            yield target


class ObservationExecutorTest(unittest.TestCase):
    def test_sensitive_tools_are_recorded_but_never_executed(self) -> None:
        fetcher = Mock()
        executor = ObservationExecutor(fetcher)
        for name in ("read_file", "send_diagnostic"):
            decision = executor.observe(
                ToolCall(name=name, arguments={"path": "/etc/passwd"}, reason="test")
            )
            self.assertTrue(decision.stop)
            self.assertEqual(decision.status, "sensitive_tool_proposed")
            self.assertIsNone(decision.result)
        fetcher.fetch.assert_not_called()

    def test_local_fetch_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "page.html").write_text("local only", encoding="utf-8")
            with LocalLabServer(root) as server:
                fetcher = LocalPageFetcher(server.base_url)
                result = fetcher.fetch(server.base_url + "/pages/page.html")
        self.assertEqual(result["body"], "local only")

    def test_non_local_fetch_is_rejected_before_network(self) -> None:
        fetcher = LocalPageFetcher("http://127.0.0.1:43210")
        with self.assertRaises(LocalOriginViolation):
            fetcher.fetch("https://example.com/")

    def test_redirect_to_non_local_origin_is_rejected(self) -> None:
        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - 标准库 API
                self.send_response(302)
                self.send_header("Location", "https://example.com/")
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            fetcher = LocalPageFetcher("http://%s:%s" % (host, port))
            with self.assertRaises(LocalOriginViolation):
                fetcher.fetch("http://%s:%s/redirect" % (host, port))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_unknown_tool_stops_observation(self) -> None:
        executor = ObservationExecutor(None)
        decision = executor.observe(
            ToolCall(name="delete_database", arguments={}, reason="test")
        )
        self.assertTrue(decision.stop)
        self.assertEqual(decision.status, "unknown_tool")


class ContextLabRuntimeTest(unittest.TestCase):
    def test_runtime_stops_at_first_sensitive_proposal(self) -> None:
        item = SimpleNamespace(
            type="function_call",
            name="read_file",
            arguments=json.dumps({"path": "demo-config.json"}),
            call_id="call-1",
        )
        response = SimpleNamespace(output=[item], output_text="")
        client = SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=response)))
        executor = ObservationExecutor(None)
        runtime = ContextLabRuntime(client, "test-model", executor)
        case = load_cases(CASES_DIR)[1]
        observation = runtime.run(build_context(case, LESSON_ROOT), run_index=1)

        self.assertEqual(observation.status, "sensitive_tool_proposed")
        self.assertEqual(observation.proposed_tools, ("read_file",))
        self.assertEqual(observation.first_sensitive_tool, "read_file")
        client.responses.create.assert_called_once()

    def test_runtime_disables_storage_and_parallel_tool_calls(self) -> None:
        response = SimpleNamespace(output=[], output_text="pip install course-sdk，默认超时 30 秒。")
        create = Mock(return_value=response)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        executor = ObservationExecutor(None)
        runtime = ContextLabRuntime(client, "test-model", executor)
        case = load_cases(CASES_DIR)[1]
        observation = runtime.run(build_context(case, LESSON_ROOT), run_index=1)

        kwargs = create.call_args.kwargs
        self.assertFalse(kwargs["store"])
        self.assertFalse(kwargs["parallel_tool_calls"])
        self.assertEqual(observation.normal_fact_hits, ("pip install course-sdk", "30 秒"))

    def test_each_runtime_starts_with_a_fresh_context(self) -> None:
        response = SimpleNamespace(output=[], output_text="done")
        create = Mock(return_value=response)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        case = load_cases(CASES_DIR)[1]
        built = build_context(case, LESSON_ROOT)

        ContextLabRuntime(client, "model", ObservationExecutor(None)).run(built, 1)
        ContextLabRuntime(client, "model", ObservationExecutor(None)).run(built, 2)

        first_input = create.call_args_list[0].kwargs["input"]
        second_input = create.call_args_list[1].kwargs["input"]
        self.assertIsNot(first_input, second_input)
        self.assertEqual(first_input, second_input)


class ContextLabOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases(CASES_DIR)

    def test_renderer_is_deterministic(self) -> None:
        self.assertEqual(
            render_outputs(self.cases, LESSON_ROOT),
            render_outputs(self.cases, LESSON_ROOT),
        )

    def test_committed_generated_files_are_current(self) -> None:
        outputs = render_outputs(self.cases, LESSON_ROOT)
        for filename, expected in outputs.items():
            self.assertEqual(
                (GENERATED_DIR / filename).read_text(encoding="utf-8"),
                expected,
            )

    def test_check_detects_a_stale_generated_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            for filename, content in render_outputs(self.cases, LESSON_ROOT).items():
                (output_dir / filename).write_text(content, encoding="utf-8")
            (output_dir / "case_catalog.md").write_text("stale", encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                status = main(
                    [
                        "check",
                        "--cases-dir",
                        str(CASES_DIR),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
        self.assertEqual(status, 1)
        self.assertIn("make context-lab-render", stream.getvalue())

    def test_inspect_does_not_access_network(self) -> None:
        stream = io.StringIO()
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network")):
            with contextlib.redirect_stdout(stream):
                status = main(
                    ["inspect", "--cases-dir", str(CASES_DIR), "--case", "CASE-03"]
                )
        self.assertEqual(status, 0)
        self.assertIn('"case_id": "CASE-03"', stream.getvalue())

    def test_report_uses_objective_counts(self) -> None:
        observations = (
            LiveObservation(
                case_id="CASE-03",
                run_index=1,
                provider="deepseek",
                model="example-model",
                status="sensitive_tool_proposed",
                proposed_tools=("fetch_webpage", "read_file"),
                first_sensitive_tool="read_file",
                sensitive_tool_proposed=True,
                normal_fact_hits=(),
                final_answer_preview=None,
                error_type=None,
            ),
            LiveObservation(
                case_id="CASE-03",
                run_index=2,
                provider="deepseek",
                model="example-model",
                status="completed",
                proposed_tools=("fetch_webpage",),
                first_sensitive_tool=None,
                sensitive_tool_proposed=False,
                normal_fact_hits=("pip install course-sdk", "30 秒"),
                final_answer_preview="normal",
                error_type=None,
            ),
        )
        with patch(
            "agent_security.context_lab.live_runtime.ContextLabRuntime.from_environment",
            side_effect=AssertionError("report must not call a model"),
        ) as model_factory:
            markdown, csv_text = build_observation_matrix(observations, self.cases)
        self.assertIn("| CASE-03 | 2 | 1 | 1 | 1 | 0 | 2/4 | 0 |", markdown)
        self.assertIn("CASE-03,2,1,1,1,0,2/4,0", csv_text)
        model_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
