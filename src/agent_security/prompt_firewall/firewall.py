"""编排规范化、检测、评分和内容准入决策。"""

import hashlib

from agent_security.content_pipeline.models import ContentEnvelope

from .detectors import RuleDetector
from .models import (
    AdmissionPolicyConfig,
    GuardFinding,
    GuardResult,
    RiskAssessment,
    RuleSet,
    ScanStatus,
)
from .normalizer import ContentNormalizer
from .scoring import ContentAdmissionPolicy, RiskScorer


class PromptFirewall:
    def __init__(self, ruleset: RuleSet, policy: AdmissionPolicyConfig) -> None:
        self.ruleset = ruleset
        self.policy_config = policy
        self.normalizer = ContentNormalizer()
        self.detector = RuleDetector(
            ruleset,
            policy.max_evidence_per_rule,
            policy.max_evidence_chars,
        )
        self.scorer = RiskScorer(policy)
        self.admission_policy = ContentAdmissionPolicy(policy)

    def inspect(self, envelope: ContentEnvelope) -> GuardResult:
        if len(envelope.content) > self.policy_config.max_content_chars:
            finding = GuardFinding(
                rule_id="PF-SCAN-001",
                category="scan_incomplete",
                severity="high",
                weight=0,
                evidence="[content omitted: length exceeded]",
                evidence_sha256=hashlib.sha256(
                    b"[content omitted: length exceeded]"
                ).hexdigest(),
                normalized_start=0,
                normalized_end=0,
                explanation="内容超过扫描上限，未进行部分扫描或静默截断。",
            )
            assessment = RiskAssessment(
                findings=(finding,),
                base_score=0,
                combination_score=0,
                risk_score=0,
                score_contributions=(),
                applied_combinations=(),
                scan_status=ScanStatus.INCOMPLETE,
            )
            decision, reason = self.admission_policy.decide(assessment)
            return GuardResult(
                decision=decision,
                decision_reason=reason,
                assessment=assessment,
                source_type=envelope.source_type,
                content_sha256=envelope.content_sha256,
                normalized_sha256="",
                normalization_transformations=(),
                ruleset_version=self.ruleset.version,
                admission_policy_version=self.policy_config.version,
            )

        normalized = self.normalizer.normalize(envelope.content)
        findings = self.detector.detect(normalized)
        assessment = self.scorer.score(findings)
        decision, reason = self.admission_policy.decide(assessment)
        return GuardResult(
            decision=decision,
            decision_reason=reason,
            assessment=assessment,
            source_type=envelope.source_type,
            content_sha256=envelope.content_sha256,
            normalized_sha256=normalized.normalized_sha256,
            normalization_transformations=normalized.transformations,
            ruleset_version=self.ruleset.version,
            admission_policy_version=self.policy_config.version,
        )
