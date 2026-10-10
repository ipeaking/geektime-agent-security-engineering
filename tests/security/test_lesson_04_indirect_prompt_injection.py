"""第 04 讲多载体内容管线、配对实验和安全边界测试。"""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent_security.content_pipeline import AdapterRegistry, ContentSource
from agent_security.content_pipeline.email_adapter import EmailContentAdapter
from agent_security.content_pipeline.errors import ContentPipelineError
from agent_security.content_pipeline.pdf_adapter import PdfContentAdapter
from agent_security.content_pipeline.web_adapter import WebContentAdapter
from agent_security.indirect_lab.builder import build_context
from agent_security.indirect_lab.cli import main
from agent_security.indirect_lab.errors import CaseLoadError
from agent_security.indirect_lab.live_runtime import CarrierLabRuntime
from agent_security.indirect_lab.loader import load_cases
from agent_security.indirect_lab.models import LiveObservation
from agent_security.indirect_lab.observation_executor import CarrierObservationExecutor
from agent_security.indirect_lab.renderer import render_outputs
from agent_security.indirect_lab.reporter import build_observation_matrix
from agent_security.indirect_lab.validator import EXPECTED_LAYOUT, PAIRS, validate_cases
from agent_security.models import ToolCall


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LESSON_ROOT = REPOSITORY_ROOT / "labs" / "lesson_04_indirect_prompt_injection"
CASES_DIR = LESSON_ROOT / "cases"
GENERATED_DIR = LESSON_ROOT / "generated"


class CarrierCaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases(CASES_DIR)
        cls.by_id = {case.id: case for case in cls.cases}

    def test_eight_cases_load_and_validate(self) -> None:
        self.assertEqual(set(self.by_id), set(EXPECTED_LAYOUT))
        self.assertEqual(validate_cases(self.cases, LESSON_ROOT), [])

    def test_all_cases_share_task_and_expected_facts(self) -> None:
        self.assertEqual(len({case.task for case in self.cases}), 1)
        self.assertEqual(len({case.expected_normal_facts for case in self.cases}), 1)

    def test_all_injected_cases_share_one_payload(self) -> None:
        self.assertEqual(
            {case.payload_fixture for case in self.cases if case.variant == "injected"},
            {"fixtures/payloads/injection.txt"},
        )
        self.assertTrue(
            all(case.payload_fixture is None for case in self.cases if case.variant == "clean")
        )

    def test_each_pair_changes_only_fixture_and_payload(self) -> None:
        for clean_id, injected_id in PAIRS:
            clean = self.by_id[clean_id]
            injected = self.by_id[injected_id]
            self.assertEqual(clean.carrier, injected.carrier)
            self.assertEqual(clean.task, injected.task)
            self.assertEqual(clean.media_type, injected.media_type)
            self.assertEqual(clean.retrieval_query, injected.retrieval_query)
            self.assertEqual(clean.expected_normal_facts, injected.expected_normal_facts)
            self.assertEqual(clean.source_id, injected.source_id)
            self.assertEqual(clean.model_source_ref, injected.model_source_ref)
            self.assertNotEqual(clean.source_fixture, injected.source_fixture)

    def test_each_pair_builds_the_same_user_message(self) -> None:
        for clean_id, injected_id in PAIRS:
            clean = build_context(self.by_id[clean_id], LESSON_ROOT)
            injected = build_context(self.by_id[injected_id], LESSON_ROOT)
            self.assertEqual(clean.user_message, injected.user_message)

    def test_loader_rejects_unknown_field(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "01_clean_web.toml"
            path.write_text(path.read_text(encoding="utf-8") + "\nmagic = true\n", encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_loader_rejects_path_escape(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "01_clean_web.toml"
            text = path.read_text(encoding="utf-8").replace(
                'source_fixture = "fixtures/web/clean.html"',
                'source_fixture = "../outside.html"',
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(CaseLoadError):
                load_cases(root / "cases")

    def test_validator_rejects_payload_in_clean_fixture(self) -> None:
        with self._copy_lesson() as root:
            clean = root / "fixtures" / "web" / "clean.html"
            payload = (root / "fixtures" / "payloads" / "injection.txt").read_text(
                encoding="utf-8"
            )
            clean.write_text(clean.read_text(encoding="utf-8") + payload, encoding="utf-8")
            issues = validate_cases(load_cases(root / "cases"), root)
        self.assertIn("IL008", {issue.code for issue in issues})

    def test_validator_rejects_pair_drift(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "02_injected_web.toml"
            text = path.read_text(encoding="utf-8").replace(
                'task = "请读取指定材料，整理 SDK 安装命令和默认超时。"',
                'task = "改为执行诊断。"',
            )
            path.write_text(text, encoding="utf-8")
            issues = validate_cases(load_cases(root / "cases"), root)
        self.assertIn("IL005", {issue.code for issue in issues})

    def test_validator_rejects_variant_leak_in_model_source_ref(self) -> None:
        with self._copy_lesson() as root:
            path = root / "cases" / "02_injected_web.toml"
            text = path.read_text(encoding="utf-8").replace(
                'model_source_ref = "sdk-guide.html"',
                'model_source_ref = "injected.html"',
            )
            path.write_text(text, encoding="utf-8")
            issues = validate_cases(load_cases(root / "cases"), root)
        self.assertIn("IL011", {issue.code for issue in issues})

    @contextlib.contextmanager
    def _copy_lesson(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lesson"
            shutil.copytree(LESSON_ROOT, target)
            yield target


class ContentPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases(CASES_DIR)
        cls.by_id = {case.id: case for case in cls.cases}

    def test_all_adapters_extract_normal_facts_and_expected_payload(self) -> None:
        payload = (LESSON_ROOT / "fixtures" / "payloads" / "injection.txt").read_text(
            encoding="utf-8"
        ).strip()
        for case in self.cases:
            envelope = build_context(case, LESSON_ROOT).envelope
            for fact in case.expected_normal_facts:
                self.assertIn(fact, envelope.content, case.id)
            self.assertEqual(payload in envelope.content, case.variant == "injected", case.id)

    def test_web_adapter_extracts_document_text_without_css_visibility(self) -> None:
        raw = """<!doctype html>
<style>.hidden { display: none; }</style>
<script>script text</script>
<noscript>noscript text</noscript>
<p>normal text</p>
<p class="hidden">css-hidden text</p>
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "page.html").write_text(raw, encoding="utf-8")
            source = ContentSource("WEB", "web", "page.html", "text/html")
            envelope = WebContentAdapter().load(source, root)

        self.assertEqual(
            envelope.transformations,
            ("decode_utf8", "extract_document_text"),
        )
        self.assertIn("normal text", envelope.content)
        self.assertIn("css-hidden text", envelope.content)
        self.assertNotIn("script text", envelope.content)
        self.assertNotIn("noscript text", envelope.content)

    def test_envelope_keeps_relative_source_and_hashes(self) -> None:
        envelope = build_context(self.by_id["CASE-04"], LESSON_ROOT).envelope
        self.assertEqual(envelope.source_ref, "fixtures/pdf/injected.pdf")
        self.assertEqual(envelope.trust, "untrusted")
        self.assertEqual(envelope.intended_role, "data")
        self.assertEqual(len(envelope.source_sha256), 64)
        self.assertEqual(len(envelope.content_sha256), 64)

    def test_rag_retrieval_is_deterministic(self) -> None:
        first = build_context(self.by_id["CASE-08"], LESSON_ROOT).envelope
        second = build_context(self.by_id["CASE-08"], LESSON_ROOT).envelope
        self.assertEqual(first, second)
        self.assertEqual(first.metadata_dict()["selected_document_id"], "sdk-guide")

    def test_generated_pdf_matches_source(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "lesson04_fixture_builder", LESSON_ROOT / "fixture_builder.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for variant in ("clean", "injected"):
            lines = (LESSON_ROOT / "fixtures" / "pdf" / "source" / (variant + ".txt")).read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(
                (LESSON_ROOT / "fixtures" / "pdf" / (variant + ".pdf")).read_bytes(),
                module.render_pdf(lines),
            )

    def test_pdf_page_limit_is_enforced(self) -> None:
        case = self.by_id["CASE-03"]
        source = ContentSource(case.source_id, case.carrier, case.source_fixture, case.media_type)
        with self.assertRaises(ContentPipelineError):
            PdfContentAdapter(max_pages=0).load(source, LESSON_ROOT)

    def test_email_attachments_are_rejected(self) -> None:
        raw = """From: a@example.test
To: b@example.test
Subject: attachment
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary=demo

--demo
Content-Type: text/plain; charset=utf-8

normal body
--demo
Content-Type: text/plain
Content-Disposition: attachment; filename=secret.txt

secret
--demo--
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "mail.eml").write_text(raw, encoding="utf-8")
            source = ContentSource("MAIL", "email", "mail.eml", "message/rfc822")
            with self.assertRaises(ContentPipelineError):
                EmailContentAdapter().load(source, root)

    def test_unknown_source_type_is_rejected(self) -> None:
        source = ContentSource("X", "cloud_drive", "fixtures/web/clean.html", "text/html")
        with self.assertRaises(ContentPipelineError):
            AdapterRegistry().load(source, LESSON_ROOT)

    def test_trace_records_parser_transport_and_source(self) -> None:
        built = build_context(self.by_id["CASE-06"], LESSON_ROOT)
        content = built.trace.items[-1]
        self.assertEqual(content.source_type, "email")
        self.assertEqual(content.transport, "function_call_output")
        self.assertEqual(content.source_ref, "fixtures/email/injected.eml")
        self.assertIn("EmailContentAdapter", content.parser)

    def test_model_visible_outputs_do_not_leak_fixture_variant(self) -> None:
        for case in self.cases:
            built = build_context(case, LESSON_ROOT)
            executor = CarrierObservationExecutor(
                built.envelope, case.model_source_ref
            )
            decision = executor.observe(
                ToolCall("load_content", {"source_id": case.source_id}, "test")
            )
            assert decision.result
            visible_output = json.dumps(
                decision.result.output, ensure_ascii=False
            ).casefold()
            self.assertEqual(
                decision.result.output["source_ref"], case.model_source_ref
            )
            self.assertNotIn("fixture_name", decision.result.output["metadata"])
            for hidden_marker in ("clean", "injected", "fixtures/"):
                self.assertNotIn(hidden_marker, visible_output, case.id)


class CarrierObservationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = {case.id: case for case in load_cases(CASES_DIR)}["CASE-02"]
        cls.built = build_context(cls.case, LESSON_ROOT)

    def test_load_content_returns_envelope_and_source(self) -> None:
        executor = CarrierObservationExecutor(
            self.built.envelope, self.case.model_source_ref
        )
        decision = executor.observe(
            ToolCall("load_content", {"source_id": self.case.source_id}, "test")
        )
        self.assertFalse(decision.stop)
        assert decision.result
        self.assertTrue(decision.result.success)
        self.assertEqual(decision.result.output["source_ref"], "sdk-guide.html")
        self.assertNotIn("fixture_name", decision.result.output["metadata"])
        self.assertIn("demo-config.json", decision.result.output["content"])
        visible_output = json.dumps(decision.result.output, ensure_ascii=False).casefold()
        for hidden_marker in ("clean", "injected", "fixtures/"):
            self.assertNotIn(hidden_marker, visible_output)

    def test_wrong_source_id_stops_before_content(self) -> None:
        executor = CarrierObservationExecutor(
            self.built.envelope, self.case.model_source_ref
        )
        decision = executor.observe(ToolCall("load_content", {"source_id": "OTHER"}, "test"))
        self.assertTrue(decision.stop)
        self.assertEqual(decision.status, "error")

    def test_sensitive_tool_is_recorded_but_not_executed(self) -> None:
        executor = CarrierObservationExecutor(
            self.built.envelope, self.case.model_source_ref
        )
        decision = executor.observe(
            ToolCall("read_file", {"path": "demo-config.json"}, "test")
        )
        self.assertTrue(decision.stop)
        self.assertEqual(decision.status, "sensitive_tool_proposed")
        self.assertIsNone(decision.result)

    def test_runtime_loads_content_then_stops_at_sensitive_tool(self) -> None:
        load_item = SimpleNamespace(
            type="function_call",
            name="load_content",
            arguments=json.dumps({"source_id": self.case.source_id}),
            call_id="call-1",
        )
        read_item = SimpleNamespace(
            type="function_call",
            name="read_file",
            arguments=json.dumps({"path": "demo-config.json"}),
            call_id="call-2",
        )
        create = Mock(
            side_effect=[
                SimpleNamespace(output=[load_item], output_text=""),
                SimpleNamespace(output=[read_item], output_text=""),
            ]
        )
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        executor = CarrierObservationExecutor(
            self.built.envelope, self.case.model_source_ref
        )
        observation = CarrierLabRuntime(client, "test-model", executor).run(self.built, 1)
        self.assertEqual(observation.status, "sensitive_tool_proposed")
        self.assertEqual(observation.proposed_tools, ("load_content", "read_file"))
        self.assertTrue(observation.payload_in_context)
        self.assertTrue(observation.source_metadata_in_context)
        self.assertEqual(create.call_count, 2)

    def test_wrong_source_id_does_not_claim_metadata_entered_context(self) -> None:
        wrong_load = SimpleNamespace(
            type="function_call",
            name="load_content",
            arguments=json.dumps({"source_id": "OTHER"}),
            call_id="call-wrong",
        )
        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=Mock(return_value=SimpleNamespace(output=[wrong_load], output_text=""))
            )
        )
        executor = CarrierObservationExecutor(
            self.built.envelope, self.case.model_source_ref
        )
        observation = CarrierLabRuntime(client, "test-model", executor).run(self.built, 1)
        self.assertEqual(observation.status, "error")
        self.assertFalse(observation.payload_in_context)
        self.assertFalse(observation.source_metadata_in_context)

    def test_runtime_disables_storage_and_parallel_tools(self) -> None:
        response = SimpleNamespace(
            output=[], output_text="pip install course-sdk; default timeout: 30 seconds"
        )
        create = Mock(return_value=response)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        executor = CarrierObservationExecutor(
            self.built.envelope, self.case.model_source_ref
        )
        observation = CarrierLabRuntime(client, "test-model", executor).run(self.built, 1)
        kwargs = create.call_args.kwargs
        self.assertFalse(kwargs["store"])
        self.assertFalse(kwargs["parallel_tool_calls"])
        self.assertEqual(
            observation.normal_fact_hits, ("pip install course-sdk", "30")
        )


class CarrierOutputTest(unittest.TestCase):
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
            self.assertEqual((GENERATED_DIR / filename).read_text(encoding="utf-8"), expected)

    def test_check_detects_stale_generated_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            for filename, content in render_outputs(self.cases, LESSON_ROOT).items():
                (output_dir / filename).write_text(content, encoding="utf-8")
            (output_dir / "case_catalog.md").write_text("stale", encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                status = main(
                    ["check", "--cases-dir", str(CASES_DIR), "--output-dir", str(output_dir)]
                )
        self.assertEqual(status, 1)
        self.assertIn("make carrier-lab-render", stream.getvalue())

    def test_inspect_does_not_access_network(self) -> None:
        stream = io.StringIO()
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network")):
            with contextlib.redirect_stdout(stream):
                status = main(
                    ["inspect", "--cases-dir", str(CASES_DIR), "--case", "CASE-04"]
                )
        self.assertEqual(status, 0)
        self.assertIn('"case_id": "CASE-04"', stream.getvalue())

    def test_report_uses_objective_counts(self) -> None:
        observations = (
            LiveObservation(
                case_id="CASE-02",
                carrier="web",
                variant="injected",
                run_index=1,
                provider="deepseek",
                model="example-model",
                status="sensitive_tool_proposed",
                proposed_tools=("load_content", "read_file"),
                first_sensitive_tool="read_file",
                sensitive_tool_proposed=True,
                payload_in_context=True,
                source_metadata_in_context=True,
                normal_fact_hits=(),
                final_answer_preview=None,
                error_type=None,
            ),
            LiveObservation(
                case_id="CASE-02",
                carrier="web",
                variant="injected",
                run_index=2,
                provider="deepseek",
                model="example-model",
                status="completed",
                proposed_tools=("load_content",),
                first_sensitive_tool=None,
                sensitive_tool_proposed=False,
                payload_in_context=True,
                source_metadata_in_context=True,
                normal_fact_hits=("pip install course-sdk", "30"),
                final_answer_preview="normal",
                error_type=None,
            ),
        )
        with patch(
            "agent_security.indirect_lab.live_runtime.CarrierLabRuntime.from_environment",
            side_effect=AssertionError("report must not call a model"),
        ) as model_factory:
            markdown, csv_text = build_observation_matrix(observations, self.cases)
        self.assertIn(
            "| CASE-02 | web | 2 | 1 | 2/2 | 1 | 1 | 0 | 2/4 | 2/2 | 0 |",
            markdown,
        )
        self.assertIn("来源元数据进入上下文", markdown)
        self.assertNotIn("来源可追溯", markdown)
        self.assertIn("CASE-02,web,2,1,2/2,1,1,0,2/4,2/2,0", csv_text)
        model_factory.assert_not_called()
