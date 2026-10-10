"""按风险类别去重计分，并应用内容准入策略。"""

from .models import (
    AdmissionPolicyConfig,
    AppliedCombination,
    DecisionReason,
    FirewallDecision,
    GuardFinding,
    RiskAssessment,
    ScanStatus,
    ScoreContribution,
)


class RiskScorer:
    def __init__(self, policy: AdmissionPolicyConfig) -> None:
        self.policy = policy

    def score(self, findings: tuple[GuardFinding, ...]) -> RiskAssessment:
        representatives: dict[str, GuardFinding] = {}
        for finding in findings:
            current = representatives.get(finding.category)
            if current is None or (finding.weight, finding.rule_id) > (
                current.weight,
                current.rule_id,
            ):
                representatives[finding.category] = finding

        contributions = tuple(
            ScoreContribution(
                contribution_id="CATEGORY:%s" % category,
                contribution_type="category",
                category=category,
                rule_id=finding.rule_id,
                score=finding.weight,
                explanation="该类别按最高权重规则计分。",
            )
            for category, finding in sorted(representatives.items())
        )
        base_score = sum(item.score for item in contributions)
        present_categories = set(representatives)
        combinations = tuple(
            AppliedCombination(
                combination_id=item.id,
                required_categories=item.required_categories,
                score=item.score,
                explanation=item.explanation,
            )
            for item in self.policy.combinations
            if set(item.required_categories).issubset(present_categories)
        )
        combination_contributions = tuple(
            ScoreContribution(
                contribution_id=item.combination_id,
                contribution_type="combination",
                category=None,
                rule_id=None,
                score=item.score,
                explanation=item.explanation,
            )
            for item in combinations
        )
        combination_score = sum(item.score for item in combinations)
        return RiskAssessment(
            findings=findings,
            base_score=base_score,
            combination_score=combination_score,
            risk_score=min(base_score + combination_score, self.policy.max_score),
            score_contributions=contributions + combination_contributions,
            applied_combinations=combinations,
            scan_status=ScanStatus.COMPLETE,
        )


class ContentAdmissionPolicy:
    def __init__(self, config: AdmissionPolicyConfig) -> None:
        self.config = config

    def decide(self, assessment: RiskAssessment) -> tuple[FirewallDecision, DecisionReason]:
        if assessment.scan_status is ScanStatus.INCOMPLETE:
            return FirewallDecision.BLOCK, DecisionReason.CONTENT_LENGTH_EXCEEDED
        if assessment.risk_score >= self.config.block_threshold:
            return FirewallDecision.BLOCK, DecisionReason.SCORE_AT_OR_ABOVE_BLOCK
        if assessment.risk_score >= self.config.flag_threshold:
            return FirewallDecision.FLAG, DecisionReason.SCORE_AT_OR_ABOVE_FLAG
        return FirewallDecision.ALLOW, DecisionReason.SCORE_BELOW_FLAG
