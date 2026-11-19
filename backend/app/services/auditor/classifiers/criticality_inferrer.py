import re

from app.core.logging import get_logger
from app.models.resource import ConfidenceLevel, CriticalityTier

logger = get_logger("auditor.classifier.criticality")

TIER1_PATTERNS = re.compile(
    r"(prod|production|prd|live|master|primary|main|critical|payment|billing|auth|identity|iam|core)",
    re.IGNORECASE,
)

TIER2_PATTERNS = re.compile(
    r"(staging|stage|stg|preprod|pre-prod|uat|qa|integration|int|shared|internal|api|gateway|data)",
    re.IGNORECASE,
)

TIER3_PATTERNS = re.compile(
    r"(dev|develop|development|test|testing|sandbox|sbx|demo|poc|experiment|tmp|temp|playground|lab)",
    re.IGNORECASE,
)


def infer_criticality(
    resource: dict,
    dependency_fan_out: int = 0,
) -> tuple[CriticalityTier, ConfidenceLevel]:
    """Infer criticality tier from name, tags, and dependency context."""
    name = resource.get("name") or ""
    tags = resource.get("tags") or {}
    arn = resource.get("arn") or ""
    config = resource.get("configuration") or {}

    signals: list[tuple[CriticalityTier, float]] = []

    tag_tier, tag_weight = _tier_from_tags(tags)
    if tag_tier:
        signals.append((tag_tier, tag_weight))

    name_tier, name_weight = _tier_from_text(name)
    if name_tier:
        signals.append((name_tier, name_weight))

    arn_tier, arn_weight = _tier_from_text(arn.split(":")[-1] if arn else "")
    if arn_tier:
        signals.append((arn_tier, arn_weight * 0.6))

    env_tag = tags.get("Environment") or tags.get("environment") or tags.get("Env") or tags.get("env") or ""
    if env_tag:
        env_tier, env_weight = _tier_from_text(env_tag)
        if env_tier:
            signals.append((env_tier, env_weight * 1.5))

    if dependency_fan_out >= 5:
        signals.append((CriticalityTier.TIER1, 0.7))
    elif dependency_fan_out >= 2:
        signals.append((CriticalityTier.TIER2, 0.5))

    db_name = config.get("DBName") or config.get("DBClusterIdentifier") or ""
    if db_name:
        db_tier, db_weight = _tier_from_text(db_name)
        if db_tier:
            signals.append((db_tier, db_weight * 0.8))

    if not signals:
        return CriticalityTier.UNCLASSIFIED, ConfidenceLevel.LOW

    tier_scores: dict[CriticalityTier, float] = {}
    for tier, weight in signals:
        tier_scores[tier] = tier_scores.get(tier, 0.0) + weight

    best_tier = max(tier_scores, key=lambda t: tier_scores[t])
    best_score = tier_scores[best_tier]

    if best_score >= 2.0:
        confidence = ConfidenceLevel.HIGH
    elif best_score >= 1.0:
        confidence = ConfidenceLevel.MEDIUM
    else:
        confidence = ConfidenceLevel.LOW

    return best_tier, confidence


def _tier_from_tags(tags: dict) -> tuple[CriticalityTier | None, float]:
    env_keys = ["Environment", "environment", "Env", "env", "Stage", "stage", "Tier", "tier"]
    for key in env_keys:
        val = tags.get(key, "")
        if val:
            tier, _ = _tier_from_text(val)
            if tier:
                return tier, 1.5
    return None, 0.0


def _tier_from_text(text: str) -> tuple[CriticalityTier | None, float]:
    if not text:
        return None, 0.0

    if TIER1_PATTERNS.search(text):
        return CriticalityTier.TIER1, 1.0

    if TIER3_PATTERNS.search(text):
        return CriticalityTier.TIER3, 1.0

    if TIER2_PATTERNS.search(text):
        return CriticalityTier.TIER2, 0.8

    return None, 0.0
