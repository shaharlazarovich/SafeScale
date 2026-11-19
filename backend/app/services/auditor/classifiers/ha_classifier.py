from app.core.logging import get_logger
from app.models.resource import ConfidenceLevel, HAClassification

logger = get_logger("auditor.classifier.ha")

BUILT_IN_SERVICES = frozenset({
    "s3", "dynamodb", "lambda", "sqs", "sns", "kms",
    "secrets_manager", "api_gateway", "cloudfront", "route53",
})


def classify_resource(
    resource: dict,
) -> tuple[HAClassification, str, ConfidenceLevel]:
    """Classify a discovered resource's HA eligibility.

    Returns:
        (classification, reason, confidence)
    """
    service = resource.get("service", "").lower()
    config = resource.get("configuration") or {}
    resource_type = resource.get("resource_type", "")

    if service in BUILT_IN_SERVICES:
        return (
            HAClassification.BUILT_IN,
            "Natively multi-AZ at no additional cost",
            ConfidenceLevel.HIGH,
        )

    classifier = _CLASSIFIERS.get(service)
    if classifier is None:
        return (
            HAClassification.INELIGIBLE,
            f"Service '{service}' not yet supported for classification",
            ConfidenceLevel.LOW,
        )

    try:
        return classifier(config, resource)
    except Exception:
        logger.exception("Classification failed for %s", resource.get("arn"))
        return (
            HAClassification.INELIGIBLE,
            "Classification error — defaulting to ineligible",
            ConfidenceLevel.LOW,
        )


def _classify_rds(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    rt = resource.get("resource_type", "")
    engine = config.get("engine", "")

    if rt == "db_cluster" or "aurora" in engine:
        return _classify_aurora_cluster(config, resource)

    multi_az = config.get("multi_az", False)
    if multi_az:
        return (
            HAClassification.ELIGIBLE,
            "Multi-AZ standby can be replaced with PITR recovery",
            ConfidenceLevel.HIGH,
        )
    return (
        HAClassification.INELIGIBLE,
        "Already single-AZ",
        ConfidenceLevel.HIGH,
    )


def _classify_aurora_cluster(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    member_count = config.get("member_count", 0)
    member_azs = config.get("member_azs", [])
    multi_az = config.get("multi_az", False) or len(member_azs) > 1

    if multi_az and member_count > 1:
        return (
            HAClassification.ELIGIBLE,
            f"Aurora cluster with {member_count} members across {len(member_azs)} AZs — replicas can be eliminated",
            ConfidenceLevel.HIGH,
        )
    if multi_az:
        return (
            HAClassification.ELIGIBLE,
            "Aurora cluster spans multiple AZs",
            ConfidenceLevel.MEDIUM,
        )
    return (
        HAClassification.INELIGIBLE,
        "Aurora cluster with single AZ — no standby replicas to remove",
        ConfidenceLevel.HIGH,
    )


def _classify_elasticache(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    automatic_failover = config.get("automatic_failover", "disabled")
    multi_az = config.get("multi_az_enabled", False)
    num_node_groups = config.get("num_node_groups", 1)
    total_nodes = config.get("total_nodes", 1)

    if multi_az or automatic_failover == "enabled":
        return (
            HAClassification.ELIGIBLE,
            "Multi-AZ replication can be replaced with S3 snapshot recovery",
            ConfidenceLevel.HIGH,
        )

    azs = config.get("availability_zones", [])
    if len(azs) > 1:
        return (
            HAClassification.ELIGIBLE,
            f"Nodes spread across {len(azs)} AZs — eligible for consolidation",
            ConfidenceLevel.MEDIUM,
        )

    if total_nodes > 1 or num_node_groups > 1:
        return (
            HAClassification.ELIGIBLE,
            "Replication group has standby replicas eligible for removal",
            ConfidenceLevel.MEDIUM,
        )

    return (
        HAClassification.INELIGIBLE,
        "Single-node cluster with no replication",
        ConfidenceLevel.HIGH,
    )


def _classify_eks(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    rt = resource.get("resource_type", "")
    azs = config.get("availability_zones", [])

    if rt == "cluster":
        if len(azs) > 1:
            return (
                HAClassification.ELIGIBLE,
                f"EKS cluster spans {len(azs)} AZs — node groups can be pinned to single AZ",
                ConfidenceLevel.MEDIUM,
            )
        return (
            HAClassification.INELIGIBLE,
            "EKS cluster already in a single AZ",
            ConfidenceLevel.MEDIUM,
        )

    if len(azs) > 1:
        return (
            HAClassification.ELIGIBLE,
            f"Node group spans {len(azs)} AZs — can be pinned to single AZ",
            ConfidenceLevel.MEDIUM,
        )

    subnet_ids = config.get("subnet_ids", [])
    if len(subnet_ids) > 1 and not azs:
        return (
            HAClassification.ELIGIBLE,
            "Node group has multiple subnets — likely multi-AZ",
            ConfidenceLevel.LOW,
        )

    return (
        HAClassification.INELIGIBLE,
        "Node group already in a single AZ",
        ConfidenceLevel.MEDIUM,
    )


def _classify_ec2(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    rt = resource.get("resource_type", "")

    if rt == "auto_scaling_group":
        azs = config.get("availability_zones", [])
        if len(azs) > 1:
            return (
                HAClassification.ELIGIBLE,
                f"ASG spans {len(azs)} AZs — can be pinned to single AZ",
                ConfidenceLevel.HIGH,
            )
        return (
            HAClassification.INELIGIBLE,
            "ASG already in a single AZ",
            ConfidenceLevel.HIGH,
        )

    if rt == "instance":
        cross_az_role = config.get("cross_az_role")
        if cross_az_role:
            return (
                HAClassification.ELIGIBLE,
                f"Instance part of cross-AZ group '{cross_az_role}'",
                ConfidenceLevel.MEDIUM,
            )
        return (
            HAClassification.INELIGIBLE,
            "Standalone instance in a single AZ",
            ConfidenceLevel.HIGH,
        )

    return (
        HAClassification.INELIGIBLE,
        "Cannot determine AZ configuration",
        ConfidenceLevel.LOW,
    )


def _classify_ebs(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    multi_az_attachment = config.get("multi_az_attachment", False)

    if multi_az_attachment:
        return (
            HAClassification.ELIGIBLE,
            "Volume attached to multi-AZ workload — savings come from parent conversion",
            ConfidenceLevel.MEDIUM,
        )

    return (
        HAClassification.INELIGIBLE,
        "EBS volumes are single-AZ; savings come from parent workload conversion",
        ConfidenceLevel.HIGH,
    )


def _classify_ecs(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    rt = resource.get("resource_type", "")
    if rt == "cluster":
        return (
            HAClassification.INELIGIBLE,
            "ECS cluster is a logical grouping — check services for AZ spread",
            ConfidenceLevel.HIGH,
        )

    azs = config.get("availability_zones", [])
    subnets = config.get("subnets", [])

    if len(azs) > 1:
        return (
            HAClassification.ELIGIBLE,
            f"ECS service tasks spread across {len(azs)} AZs — can be consolidated",
            ConfidenceLevel.MEDIUM,
        )

    if len(subnets) > 1 and not azs:
        return (
            HAClassification.ELIGIBLE,
            "ECS service uses multiple subnets — likely multi-AZ",
            ConfidenceLevel.LOW,
        )

    return (
        HAClassification.INELIGIBLE,
        "ECS service already in a single AZ",
        ConfidenceLevel.MEDIUM,
    )


def _classify_elb(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    cross_az = config.get("cross_az_data_transfer", False)
    azs = config.get("availability_zones", [])

    if cross_az:
        return (
            HAClassification.ELIGIBLE,
            f"Load balancer has cross-AZ data transfer across {len(azs)} AZs — transfer costs can be reduced",
            ConfidenceLevel.HIGH,
        )

    return (
        HAClassification.BUILT_IN,
        "Load balancer is natively multi-AZ; no cross-AZ transfer costs detected",
        ConfidenceLevel.HIGH,
    )


def _classify_opensearch(config: dict, resource: dict) -> tuple[HAClassification, str, ConfidenceLevel]:
    zone_awareness = config.get("zone_awareness_enabled", False)
    az_count = config.get("availability_zone_count", 1)

    if zone_awareness and az_count > 1:
        return (
            HAClassification.ELIGIBLE,
            f"OpenSearch cluster has zone awareness across {az_count} AZs — can be converted to single-AZ",
            ConfidenceLevel.HIGH,
        )

    return (
        HAClassification.INELIGIBLE,
        "OpenSearch cluster already single-zone",
        ConfidenceLevel.HIGH,
    )


_CLASSIFIERS = {
    "rds": _classify_rds,
    "elasticache": _classify_elasticache,
    "eks": _classify_eks,
    "ec2": _classify_ec2,
    "ebs": _classify_ebs,
    "ecs": _classify_ecs,
    "elb": _classify_elb,
    "opensearch": _classify_opensearch,
}
