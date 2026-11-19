"""Unit tests for criticality tier inference."""

from app.models.resource import ConfidenceLevel, CriticalityTier
from app.services.auditor.classifiers.criticality_inferrer import infer_criticality


class TestNameBasedInference:
    def test_production_name_tier1(self):
        resource = {"name": "prod-api-db", "arn": "arn:aws:rds:us-east-1:123:db:prod-api-db", "tags": {}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER1

    def test_staging_name_tier2(self):
        resource = {"name": "staging-cache", "arn": "arn:aws:elasticache:us-east-1:123:rg:staging-cache", "tags": {}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER2

    def test_dev_name_tier3(self):
        resource = {"name": "dev-test-db", "arn": "arn:aws:rds:us-east-1:123:db:dev-test-db", "tags": {}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER3

    def test_sandbox_name_tier3(self):
        resource = {"name": "sandbox-experiment", "arn": "arn:aws:rds:us-east-1:123:db:sandbox", "tags": {}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER3

    def test_no_signals_unclassified(self):
        resource = {"name": "abc123", "arn": "arn:aws:rds:us-east-1:123:db:abc123", "tags": {}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.UNCLASSIFIED
        assert confidence == ConfidenceLevel.LOW


class TestTagBasedInference:
    def test_env_tag_production(self):
        resource = {"name": "my-db", "arn": "arn:aws:rds:us-east-1:123:db:my-db", "tags": {"Environment": "production"}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER1
        assert confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_env_tag_staging(self):
        resource = {"name": "my-cache", "arn": "arn:aws:rds:us-east-1:123:db:my-cache", "tags": {"Env": "staging"}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER2

    def test_env_tag_dev(self):
        resource = {"name": "my-db", "arn": "arn:aws:rds:us-east-1:123:db:my-db", "tags": {"environment": "development"}}
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER3

    def test_tag_overrides_name(self):
        resource = {
            "name": "dev-misleading-name",
            "arn": "arn:aws:rds:us-east-1:123:db:dev-misleading-name",
            "tags": {"Environment": "production"},
        }
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER1


class TestDependencyBasedInference:
    def test_high_fan_out_boosts_to_tier1(self):
        resource = {"name": "central-db", "arn": "arn:aws:rds:us-east-1:123:db:central-db", "tags": {}}
        tier, confidence = infer_criticality(resource, dependency_fan_out=5)
        assert tier == CriticalityTier.TIER1

    def test_medium_fan_out_suggests_tier2(self):
        resource = {"name": "some-service", "arn": "arn:aws:ecs:us-east-1:123:svc:some-service", "tags": {}}
        tier, confidence = infer_criticality(resource, dependency_fan_out=3)
        assert tier == CriticalityTier.TIER2


class TestConfigBasedInference:
    def test_db_name_with_prod(self):
        resource = {
            "name": "my-rds-instance",
            "arn": "arn:aws:rds:us-east-1:123:db:my-rds-instance",
            "tags": {},
            "configuration": {"DBName": "production_core"},
        }
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER1

    def test_db_cluster_identifier_with_dev(self):
        resource = {
            "name": "random-name",
            "arn": "arn:aws:rds:us-east-1:123:db:random-name",
            "tags": {},
            "configuration": {"DBClusterIdentifier": "dev-analytics"},
        }
        tier, confidence = infer_criticality(resource)
        assert tier == CriticalityTier.TIER3
