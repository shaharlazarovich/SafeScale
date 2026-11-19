"""Unit tests for HA classification logic."""

import pytest

from app.models.resource import ConfidenceLevel, HAClassification
from app.services.auditor.classifiers.ha_classifier import classify_resource


class TestRDSClassification:
    def test_rds_multi_az_is_eligible(self):
        resource = {
            "service": "rds",
            "resource_type": "db_instance",
            "arn": "arn:aws:rds:us-east-1:123456789012:db:prod-main",
            "configuration": {"multi_az": True, "db_instance_class": "db.r6g.2xlarge", "engine": "postgres"},
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE
        assert "PITR" in reason or "standby" in reason.lower()
        assert confidence == ConfidenceLevel.HIGH

    def test_rds_single_az_ineligible(self):
        resource = {
            "service": "rds",
            "resource_type": "db_instance",
            "arn": "arn:aws:rds:us-east-1:123456789012:db:dev-db",
            "configuration": {"multi_az": False, "db_instance_class": "db.t3.medium", "engine": "mysql"},
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE
        assert confidence == ConfidenceLevel.HIGH

    def test_aurora_cluster_multi_az_eligible(self):
        resource = {
            "service": "rds",
            "resource_type": "db_cluster",
            "arn": "arn:aws:rds:us-east-1:123456789012:cluster:aurora-prod",
            "configuration": {
                "engine": "aurora-postgresql",
                "multi_az": True,
                "member_count": 3,
                "member_azs": ["us-east-1a", "us-east-1b"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE
        assert confidence == ConfidenceLevel.HIGH

    def test_aurora_cluster_single_az_ineligible(self):
        resource = {
            "service": "rds",
            "resource_type": "db_cluster",
            "arn": "arn:aws:rds:us-east-1:123456789012:cluster:aurora-dev",
            "configuration": {
                "engine": "aurora-mysql",
                "multi_az": False,
                "member_count": 1,
                "member_azs": ["us-east-1a"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE


class TestElastiCacheClassification:
    def test_multi_az_enabled_eligible(self):
        resource = {
            "service": "elasticache",
            "resource_type": "replication_group",
            "arn": "arn:aws:elasticache:us-east-1:123456789012:replicationgroup:redis-session",
            "configuration": {
                "automatic_failover": "enabled",
                "multi_az_enabled": True,
                "num_node_groups": 1,
                "total_nodes": 3,
                "availability_zones": ["us-east-1a", "us-east-1b"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE
        assert confidence == ConfidenceLevel.HIGH

    def test_single_node_ineligible(self):
        resource = {
            "service": "elasticache",
            "resource_type": "replication_group",
            "arn": "arn:aws:elasticache:us-east-1:123456789012:replicationgroup:redis-cache",
            "configuration": {
                "automatic_failover": "disabled",
                "multi_az_enabled": False,
                "num_node_groups": 1,
                "total_nodes": 1,
                "availability_zones": ["us-east-1a"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE

    def test_multi_az_nodes_detected(self):
        resource = {
            "service": "elasticache",
            "resource_type": "replication_group",
            "arn": "arn:aws:elasticache:us-east-1:123456789012:replicationgroup:redis-multi",
            "configuration": {
                "automatic_failover": "disabled",
                "multi_az_enabled": False,
                "num_node_groups": 1,
                "total_nodes": 2,
                "availability_zones": ["us-east-1a", "us-east-1b"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE


class TestEKSClassification:
    def test_nodegroup_multi_az_eligible(self):
        resource = {
            "service": "eks",
            "resource_type": "nodegroup",
            "arn": "arn:aws:eks:us-east-1:123456789012:nodegroup/cluster/workers/abc123",
            "configuration": {
                "availability_zones": ["us-east-1a", "us-east-1b", "us-east-1c"],
                "instance_types": ["m6i.2xlarge"],
                "scaling_config": {"desired_size": 6},
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE
        assert "3 AZs" in reason

    def test_nodegroup_single_az_ineligible(self):
        resource = {
            "service": "eks",
            "resource_type": "nodegroup",
            "arn": "arn:aws:eks:us-east-1:123456789012:nodegroup/cluster/batch/xyz789",
            "configuration": {
                "availability_zones": ["us-east-1a"],
                "instance_types": ["c6i.xlarge"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE

    def test_cluster_multi_az_eligible(self):
        resource = {
            "service": "eks",
            "resource_type": "cluster",
            "arn": "arn:aws:eks:us-east-1:123456789012:cluster/prod",
            "configuration": {
                "availability_zones": ["us-east-1a", "us-east-1b"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE


class TestEC2Classification:
    def test_asg_multi_az_eligible(self):
        resource = {
            "service": "ec2",
            "resource_type": "auto_scaling_group",
            "arn": "arn:aws:autoscaling:us-east-1:123456789012:autoScalingGroup:abc",
            "configuration": {
                "availability_zones": ["us-east-1a", "us-east-1b"],
                "desired_capacity": 4,
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE
        assert confidence == ConfidenceLevel.HIGH

    def test_asg_single_az_ineligible(self):
        resource = {
            "service": "ec2",
            "resource_type": "auto_scaling_group",
            "arn": "arn:aws:autoscaling:us-east-1:123456789012:autoScalingGroup:xyz",
            "configuration": {"availability_zones": ["us-east-1a"]},
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE

    def test_instance_cross_az_role_eligible(self):
        resource = {
            "service": "ec2",
            "resource_type": "instance",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-abc",
            "configuration": {"cross_az_role": "web-tier", "instance_type": "m5.large"},
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE


class TestECSClassification:
    def test_service_multi_az_eligible(self):
        resource = {
            "service": "ecs",
            "resource_type": "service",
            "arn": "arn:aws:ecs:us-east-1:123456789012:service/cluster/api",
            "configuration": {
                "availability_zones": ["us-east-1a", "us-east-1b"],
                "desired_count": 4,
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE

    def test_cluster_object_ineligible(self):
        resource = {
            "service": "ecs",
            "resource_type": "cluster",
            "arn": "arn:aws:ecs:us-east-1:123456789012:cluster/prod",
            "configuration": {},
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE


class TestOpenSearchClassification:
    def test_zone_aware_eligible(self):
        resource = {
            "service": "opensearch",
            "resource_type": "domain",
            "arn": "arn:aws:es:us-east-1:123456789012:domain/logs",
            "configuration": {
                "zone_awareness_enabled": True,
                "availability_zone_count": 3,
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE
        assert confidence == ConfidenceLevel.HIGH

    def test_single_zone_ineligible(self):
        resource = {
            "service": "opensearch",
            "resource_type": "domain",
            "arn": "arn:aws:es:us-east-1:123456789012:domain/dev-logs",
            "configuration": {
                "zone_awareness_enabled": False,
                "availability_zone_count": 1,
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE


class TestELBClassification:
    def test_cross_az_transfer_eligible(self):
        resource = {
            "service": "elb",
            "resource_type": "application",
            "arn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/prod/abc",
            "configuration": {
                "cross_az_data_transfer": True,
                "availability_zones": ["us-east-1a", "us-east-1b"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.ELIGIBLE

    def test_no_cross_az_built_in(self):
        resource = {
            "service": "elb",
            "resource_type": "application",
            "arn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/internal/xyz",
            "configuration": {
                "cross_az_data_transfer": False,
                "availability_zones": ["us-east-1a"],
            },
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.BUILT_IN


class TestBuiltInServices:
    @pytest.mark.parametrize("service", ["s3", "dynamodb", "lambda", "sqs", "sns", "kms"])
    def test_built_in_services(self, service):
        resource = {
            "service": service,
            "resource_type": "thing",
            "arn": f"arn:aws:{service}:us-east-1:123456789012:thing/abc",
            "configuration": {},
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.BUILT_IN
        assert confidence == ConfidenceLevel.HIGH


class TestUnknownService:
    def test_unknown_service_ineligible(self):
        resource = {
            "service": "unknown_service",
            "resource_type": "thing",
            "arn": "arn:aws:unknown:us-east-1:123456789012:thing/abc",
            "configuration": {},
        }
        classification, reason, confidence = classify_resource(resource)
        assert classification == HAClassification.INELIGIBLE
        assert confidence == ConfidenceLevel.LOW
