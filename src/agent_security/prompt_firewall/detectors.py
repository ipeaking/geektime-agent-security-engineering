"""使用受限、确定性的规则语言扫描规范化文本。"""

import hashlib
import re
from typing import Iterable

from .models import FirewallRule, GuardFinding, NormalizedContent, PatternType, RuleSet
from .normalizer import ContentNormalizer


TOKEN_VALUE = re.compile(
    r"(?i)\b(api[_ -]?key|token|password)\s*([:=])\s*([^\s,;]+)"
)
OPENAI_STYLE_TOKEN = re.compile(r"(?i)\bsk-[a-z0-9_-]{6,}")


class RuleDetector:
    def __init__(
        self,
        ruleset: RuleSet,
        max_evidence_per_rule: int,
        max_evidence_chars: int,
    ) -> None:
        self.ruleset = ruleset
        self.max_evidence_per_rule = max_evidence_per_rule
        self.max_evidence_chars = max_evidence_chars
        self.pattern_normalizer = ContentNormalizer()

    def detect(self, normalized: NormalizedContent) -> tuple[GuardFinding, ...]:
        findings: list[GuardFinding] = []
        for rule in sorted(self.ruleset.rules, key=lambda item: item.id):
            if not rule.enabled:
                continue
            matches = (
                self._literal_matches(normalized.text, rule.patterns)
                if rule.pattern_type is PatternType.LITERAL
                else self._bounded_matches(normalized.text, rule)
            )
            for start, end in list(matches)[: self.max_evidence_per_rule]:
                raw_evidence = normalized.text[start:end]
                findings.append(
                    GuardFinding(
                        rule_id=rule.id,
                        category=rule.category,
                        severity=rule.severity,
                        weight=rule.weight,
                        evidence=self._redact(raw_evidence)[: self.max_evidence_chars],
                        evidence_sha256=hashlib.sha256(
                            raw_evidence.encode("utf-8")
                        ).hexdigest(),
                        normalized_start=start,
                        normalized_end=end,
                        explanation=rule.explanation,
                    )
                )
        return tuple(
            sorted(findings, key=lambda item: (item.rule_id, item.normalized_start, item.normalized_end))
        )

    def _literal_matches(self, text: str, patterns: tuple[str, ...]) -> Iterable[tuple[int, int]]:
        seen: set[tuple[int, int]] = set()
        for pattern in patterns:
            needle = self.pattern_normalizer.normalize(pattern).text
            start = 0
            while True:
                index = text.find(needle, start)
                if index < 0:
                    break
                span = (index, index + len(needle))
                if span not in seen:
                    seen.add(span)
                    yield span
                start = index + max(1, len(needle))

    def _bounded_matches(self, text: str, rule: FirewallRule) -> Iterable[tuple[int, int]]:
        seen: set[tuple[int, int]] = set()
        for leading in rule.leading_terms:
            lead = self.pattern_normalizer.normalize(leading).text
            start = 0
            while True:
                lead_index = text.find(lead, start)
                if lead_index < 0:
                    break
                search_start = lead_index + len(lead)
                search_end = min(len(text), search_start + rule.max_gap_chars)
                candidates: list[tuple[int, int]] = []
                for target in rule.target_terms:
                    target_text = self.pattern_normalizer.normalize(target).text
                    target_index = text.find(target_text, search_start, search_end + len(target_text))
                    if target_index >= 0 and target_index - search_start <= rule.max_gap_chars:
                        candidates.append((target_index, target_index + len(target_text)))
                if candidates:
                    target_start, target_end = min(candidates)
                    span = (lead_index, target_end)
                    if span not in seen:
                        seen.add(span)
                        yield span
                start = lead_index + max(1, len(lead))

    @staticmethod
    def _redact(value: str) -> str:
        value = OPENAI_STYLE_TOKEN.sub("sk-***redacted***", value)
        return TOKEN_VALUE.sub(lambda match: "%s%s***redacted***" % (match[1], match[2]), value)
