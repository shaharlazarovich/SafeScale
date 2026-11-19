from decimal import Decimal

from app.core.logging import get_logger
from app.models.resource import HAClassification

logger = get_logger("auditor.classifier.cost")

HOURLY_PRICING: dict[str, dict[str, Decimal]] = {
    "rds": {
        "db.t3.micro": Decimal("0.017"),
        "db.t3.small": Decimal("0.034"),
        "db.t3.medium": Decimal("0.068"),
        "db.t3.large": Decimal("0.136"),
        "db.t3.xlarge": Decimal("0.272"),
        "db.t3.2xlarge": Decimal("0.544"),
        "db.r5.large": Decimal("0.250"),
        "db.r5.xlarge": Decimal("0.500"),
        "db.r5.2xlarge": Decimal("1.000"),
        "db.r5.4xlarge": Decimal("2.000"),
        "db.r6g.large": Decimal("0.228"),
        "db.r6g.xlarge": Decimal("0.456"),
        "db.r6g.2xlarge": Decimal("0.912"),
        "db.m5.large": Decimal("0.171"),
        "db.m5.xlarge": Decimal("0.342"),
        "db.m5.2xlarge": Decimal("0.684"),
        "db.m6g.large": Decimal("0.156"),
        "db.m6g.xlarge": Decimal("0.312"),
    },
    "elasticache": {
        "cache.t3.micro": Decimal("0.017"),
        "cache.t3.small": Decimal("0.034"),
        "cache.t3.medium": Decimal("0.068"),
        "cache.r6g.large": Decimal("0.226"),
        "cache.r6g.xlarge": Decimal("0.451"),
        "cache.r6g.2xlarge": Decimal("0.903"),
        "cache.r5.large": Decimal("0.248"),
        "cache.r5.xlarge": Decimal("0.496"),
        "cache.m5.large": Decimal("0.156"),
        "cache.m5.xlarge": Decimal("0.311"),
    },
    "opensearch": {
        "t3.small.search": Decimal("0.036"),
        "t3.medium.search": Decimal("0.073"),
        "m5.large.search": Decimal("0.142"),
        "m5.xlarge.search": Decimal("0.284"),
        "m5.2xlarge.search": Decimal("0.568"),
        "r5.large.search": Decimal("0.186"),
        "r5.xlarge.search": Decimal("0.372"),
        "r5.2xlarge.search": Decimal("0.744"),
        "r6g.large.search": Decimal("0.167"),
        "r6g.xlarge.search": Decimal("0.335"),
    },
    "ec2": {
        "t3.micro": Decimal("0.0104"),
        "t3.small": Decimal("0.0208"),
        "t3.medium": Decimal("0.0416"),
        "t3.large": Decimal("0.0832"),
        "t3.xlarge": Decimal("0.1664"),
        "m5.large": Decimal("0.096"),
        "m5.xlarge": Decimal("0.192"),
        "m5.2xlarge": Decimal("0.384"),
        "m6i.large": Decimal("0.096"),
        "m6i.xlarge": Decimal("0.192"),
        "c5.large": Decimal("0.085"),
        "c5.xlarge": Decimal("0.170"),
        "r5.large": Decimal("0.126"),
        "r5.xlarge": Decimal("0.252"),
    },
}

EBS_GB_MONTH: dict[str, Decimal] = {
    "gp2": Decimal("0.10"),
    "gp3": Decimal("0.08"),
    "io1": Decimal("0.125"),
    "io2": Decimal("0.125"),
    "st1": Decimal("0.045"),
    "sc1": Decimal("0.015"),
    "standard": Decimal("0.05"),
}

HOURS_PER_MONTH = Decimal("730")


def estimate_costs(
    resource: dict,
    ha_classification: HAClassification = HAClassification.INELIGIBLE,
) -> tuple[Decimal | None, Decimal | None]:
    """Estimate monthly cost and potential savings.

    Returns:
        (monthly_cost, estimated_savings) — either can be None if unpriceable.
    """
    service = resource.get("service", "").lower()
    config = resource.get("configuration") or {}

    estimator = _ESTIMATORS.get(service)
    if estimator is None:
        return None, None

    try:
        return estimator(config, resource, ha_classification)
    except Exception:
        logger.exception("Cost estimation failed for %s", resource.get("arn"))
        return None, None


def _instance_monthly_cost(service_key: str, instance_class: str) -> Decimal | None:
    prices = HOURLY_PRICING.get(service_key, {})
    hourly = prices.get(instance_class)
    if hourly is None:
        for key, val in prices.items():
            if key in instance_class or instance_class in key:
                hourly = val
                break
    if hourly is None:
        return None
    return (hourly * HOURS_PER_MONTH).quantize(Decimal("0.01"))


def _estimate_rds(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    rt = resource.get("resource_type", "")

    if rt == "db_cluster":
        return _estimate_aurora_cluster(config, resource, classification)

    instance_class = config.get("db_instance_class", "")
    monthly = _instance_monthly_cost("rds", instance_class)
    if monthly is None:
        return None, None

    multi_az = config.get("multi_az", False)
    if multi_az:
        total = monthly * 2
        savings = monthly if classification == HAClassification.ELIGIBLE else Decimal("0")
        return total, savings

    return monthly, Decimal("0")


def _estimate_aurora_cluster(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    instance_class = config.get("db_instance_class", "")
    if not instance_class:
        return None, None

    per_instance = _instance_monthly_cost("rds", instance_class)
    if per_instance is None:
        return None, None

    member_count = config.get("member_count", 1)
    total = per_instance * max(member_count, 1)

    if classification == HAClassification.ELIGIBLE and member_count > 1:
        savings = per_instance * (member_count - 1)
    else:
        savings = Decimal("0")

    return total, savings


def _estimate_elasticache(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    node_type = config.get("node_type", "")
    per_node = _instance_monthly_cost("elasticache", node_type)
    if per_node is None:
        return None, None

    total_nodes = config.get("total_nodes", 1)
    num_shards = config.get("num_node_groups", 1)
    total = per_node * max(total_nodes, 1)

    if classification == HAClassification.ELIGIBLE and total_nodes > num_shards:
        replica_nodes = total_nodes - num_shards
        savings = per_node * replica_nodes
    else:
        savings = Decimal("0")

    return total, savings


def _estimate_eks(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    rt = resource.get("resource_type", "")
    if rt == "cluster":
        return Decimal("73.00"), Decimal("0")

    instance_types = config.get("instance_types", [])
    desired = config.get("scaling_config", {}).get("desired_size", 0)
    if not instance_types or not desired:
        return None, None

    hourly = HOURLY_PRICING.get("ec2", {}).get(instance_types[0])
    if hourly is None:
        for key, val in HOURLY_PRICING.get("ec2", {}).items():
            if key in instance_types[0] or instance_types[0] in key:
                hourly = val
                break
    if hourly is None:
        return None, None

    monthly = (hourly * HOURS_PER_MONTH * desired).quantize(Decimal("0.01"))
    azs = config.get("availability_zones", [])
    az_count = max(len(azs), 1)

    if az_count > 1 and classification == HAClassification.ELIGIBLE:
        reducible = desired - max(desired // az_count, 1)
        savings = (hourly * HOURS_PER_MONTH * reducible).quantize(Decimal("0.01"))
    else:
        savings = Decimal("0")

    return monthly, savings


def _estimate_ec2(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    rt = resource.get("resource_type", "")

    if rt == "auto_scaling_group":
        azs = config.get("availability_zones", [])
        desired = config.get("desired_capacity", 0)
        instance_type_raw = config.get("instance_type", "")
        if instance_type_raw.startswith("lt:") or instance_type_raw.startswith("lc:") or "," in instance_type_raw:
            return None, None

        hourly = HOURLY_PRICING.get("ec2", {}).get(instance_type_raw)
        if hourly is None or not desired:
            return None, None

        monthly = (hourly * HOURS_PER_MONTH * desired).quantize(Decimal("0.01"))
        if classification == HAClassification.ELIGIBLE and len(azs) > 1:
            reducible = desired - max(desired // len(azs), 1)
            savings = (hourly * HOURS_PER_MONTH * reducible).quantize(Decimal("0.01"))
        else:
            savings = Decimal("0")
        return monthly, savings

    if rt == "instance":
        instance_type = config.get("instance_type", "")
        hourly = HOURLY_PRICING.get("ec2", {}).get(instance_type)
        if hourly is None:
            return None, None
        monthly = (hourly * HOURS_PER_MONTH).quantize(Decimal("0.01"))
        return monthly, Decimal("0")

    return None, None


def _estimate_ecs(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    rt = resource.get("resource_type", "")
    if rt == "cluster":
        return None, None

    cpu_raw = config.get("cpu")
    memory_raw = config.get("memory")
    desired = config.get("desired_count", 0)
    if not cpu_raw or not desired:
        return None, None

    cpu_val = int(cpu_raw) / 1024
    mem_val = int(memory_raw or 512) / 1024

    per_task_hourly = Decimal(str(cpu_val)) * Decimal("0.04048") + Decimal(str(mem_val)) * Decimal("0.004445")
    monthly = (per_task_hourly * HOURS_PER_MONTH * desired).quantize(Decimal("0.01"))

    azs = config.get("availability_zones", [])
    if len(azs) > 1 and classification == HAClassification.ELIGIBLE:
        reducible = desired - max(desired // len(azs), 1)
        savings = (per_task_hourly * HOURS_PER_MONTH * reducible).quantize(Decimal("0.01"))
    else:
        savings = Decimal("0")

    return monthly, savings


def _estimate_opensearch(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    instance_type = config.get("instance_type", "")
    instance_count = config.get("instance_count", 1)

    per_node = _instance_monthly_cost("opensearch", instance_type)
    if per_node is None:
        return None, None

    total = per_node * instance_count

    if classification == HAClassification.ELIGIBLE:
        az_count = config.get("availability_zone_count", 1)
        if az_count > 1:
            reducible = instance_count - max(instance_count // az_count, 1)
            savings = per_node * reducible
        else:
            savings = Decimal("0")
    else:
        savings = Decimal("0")

    return total, savings


def _estimate_ebs(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    vol_type = config.get("volume_type", "gp3").lower()
    size_gb = config.get("size_gb", 0)
    if not size_gb:
        return None, None

    price_per_gb = EBS_GB_MONTH.get(vol_type, Decimal("0.10"))
    monthly = (price_per_gb * Decimal(str(size_gb))).quantize(Decimal("0.01"))
    return monthly, Decimal("0")


def _estimate_elb(config: dict, resource: dict, classification: HAClassification) -> tuple[Decimal | None, Decimal | None]:
    monthly_base = Decimal("16.43")
    cross_az = config.get("cross_az_data_transfer", False)
    cross_az_savings = Decimal("5.00") if cross_az else Decimal("0")
    return monthly_base, cross_az_savings


_ESTIMATORS = {
    "rds": _estimate_rds,
    "elasticache": _estimate_elasticache,
    "eks": _estimate_eks,
    "ec2": _estimate_ec2,
    "ecs": _estimate_ecs,
    "opensearch": _estimate_opensearch,
    "ebs": _estimate_ebs,
    "elb": _estimate_elb,
}
