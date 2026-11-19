"""Unit tests for cost calculation and savings estimation."""

from decimal import Decimal

import pytest

from app.models.resource import HAClassification
from app.services.auditor.classifiers.cost_calculator import estimate_costs


class TestRDSCosts:
    def test_rds_multi_az_savings(self):
        resource = {
            "service": "rds",
            "resource_type": "db_instance",
            "arn": "arn:aws:rds:us-east-1:123456789012:db:prod-main",
            "configuration": {
                "db_instance_class": "db.r5.large",
                "multi_az": True,
                "engine": "postgres",
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.ELIGIBLE)
        assert monthly is not None
        assert savings is not None
        assert savings > 0
        assert savings == monthly / 2

    def test_rds_single_az_no_savings(self):
        resource = {
            "service": "rds",
            "resource_type": "db_instance",
            "arn": "arn:aws:rds:us-east-1:123456789012:db:dev-db",
            "configuration": {
                "db_instance_class": "db.t3.medium",
                "multi_az": False,
                "engine": "mysql",
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly is not None
        assert savings == Decimal("0")

    def test_aurora_cluster_savings(self):
        resource = {
            "service": "rds",
            "resource_type": "db_cluster",
            "arn": "arn:aws:rds:us-east-1:123456789012:cluster:aurora-prod",
            "configuration": {
                "db_instance_class": "db.r5.large",
                "engine": "aurora-postgresql",
                "member_count": 3,
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.ELIGIBLE)
        assert monthly is not None
        assert savings is not None
        per_instance = Decimal("0.250") * Decimal("730")
        assert monthly == (per_instance * 3).quantize(Decimal("0.01"))
        assert savings == (per_instance * 2).quantize(Decimal("0.01"))


class TestElastiCacheCosts:
    def test_elasticache_multi_az_savings(self):
        resource = {
            "service": "elasticache",
            "resource_type": "replication_group",
            "arn": "arn:aws:elasticache:us-east-1:123456789012:replicationgroup:redis",
            "configuration": {
                "node_type": "cache.r6g.large",
                "num_node_groups": 1,
                "total_nodes": 3,
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.ELIGIBLE)
        assert monthly is not None
        assert savings is not None
        per_node = Decimal("0.226") * Decimal("730")
        assert savings == (per_node * 2).quantize(Decimal("0.01"))

    def test_elasticache_single_node_no_savings(self):
        resource = {
            "service": "elasticache",
            "resource_type": "replication_group",
            "arn": "arn:aws:elasticache:us-east-1:123456789012:replicationgroup:cache",
            "configuration": {
                "node_type": "cache.t3.medium",
                "num_node_groups": 1,
                "total_nodes": 1,
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly is not None
        assert savings == Decimal("0")


class TestEKSCosts:
    def test_eks_nodegroup_multi_az_savings(self):
        resource = {
            "service": "eks",
            "resource_type": "nodegroup",
            "arn": "arn:aws:eks:us-east-1:123456789012:nodegroup/cluster/workers/abc",
            "configuration": {
                "instance_types": ["m5.large"],
                "scaling_config": {"desired_size": 6},
                "availability_zones": ["us-east-1a", "us-east-1b", "us-east-1c"],
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.ELIGIBLE)
        assert monthly is not None
        assert savings is not None
        assert savings > 0

    def test_eks_cluster_fixed_cost(self):
        resource = {
            "service": "eks",
            "resource_type": "cluster",
            "arn": "arn:aws:eks:us-east-1:123456789012:cluster/prod",
            "configuration": {},
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly == Decimal("73.00")
        assert savings == Decimal("0")


class TestECSCosts:
    def test_ecs_fargate_multi_az_savings(self):
        resource = {
            "service": "ecs",
            "resource_type": "service",
            "arn": "arn:aws:ecs:us-east-1:123456789012:service/cluster/api",
            "configuration": {
                "cpu": "1024",
                "memory": "2048",
                "desired_count": 4,
                "availability_zones": ["us-east-1a", "us-east-1b"],
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.ELIGIBLE)
        assert monthly is not None
        assert savings is not None
        assert savings > 0

    def test_ecs_cluster_returns_none(self):
        resource = {
            "service": "ecs",
            "resource_type": "cluster",
            "arn": "arn:aws:ecs:us-east-1:123456789012:cluster/prod",
            "configuration": {},
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly is None


class TestOpenSearchCosts:
    def test_opensearch_zone_aware_savings(self):
        resource = {
            "service": "opensearch",
            "resource_type": "domain",
            "arn": "arn:aws:es:us-east-1:123456789012:domain/logs",
            "configuration": {
                "instance_type": "r5.large.search",
                "instance_count": 6,
                "zone_awareness_enabled": True,
                "availability_zone_count": 3,
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.ELIGIBLE)
        assert monthly is not None
        assert savings is not None
        assert savings > 0

    def test_opensearch_single_zone_no_savings(self):
        resource = {
            "service": "opensearch",
            "resource_type": "domain",
            "arn": "arn:aws:es:us-east-1:123456789012:domain/dev",
            "configuration": {
                "instance_type": "t3.small.search",
                "instance_count": 1,
                "zone_awareness_enabled": False,
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly is not None
        assert savings == Decimal("0")


class TestEBSCosts:
    def test_ebs_gp3_cost(self):
        resource = {
            "service": "ebs",
            "resource_type": "volume",
            "arn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-abc",
            "configuration": {"volume_type": "gp3", "size_gb": 100},
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly == Decimal("8.00")
        assert savings == Decimal("0")

    def test_ebs_io2_cost(self):
        resource = {
            "service": "ebs",
            "resource_type": "volume",
            "arn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-xyz",
            "configuration": {"volume_type": "io2", "size_gb": 500},
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly == Decimal("62.50")


class TestEC2Costs:
    def test_asg_multi_az_savings(self):
        resource = {
            "service": "ec2",
            "resource_type": "auto_scaling_group",
            "arn": "arn:aws:autoscaling:us-east-1:123456789012:autoScalingGroup:abc",
            "configuration": {
                "instance_type": "m5.large",
                "desired_capacity": 4,
                "availability_zones": ["us-east-1a", "us-east-1b"],
            },
        }
        monthly, savings = estimate_costs(resource, HAClassification.ELIGIBLE)
        assert monthly is not None
        assert savings is not None
        assert savings > 0


class TestUnknownService:
    def test_unknown_service_returns_none(self):
        resource = {
            "service": "unknown",
            "resource_type": "thing",
            "arn": "arn:aws:unknown:us-east-1:123456789012:thing/abc",
            "configuration": {},
        }
        monthly, savings = estimate_costs(resource, HAClassification.INELIGIBLE)
        assert monthly is None
        assert savings is None
