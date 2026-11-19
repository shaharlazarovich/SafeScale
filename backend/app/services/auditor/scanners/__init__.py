from .base import BaseScanner
from .ebs import EBSScanner
from .ec2 import EC2Scanner
from .ecs import ECSScanner
from .eks import EKSScanner
from .elasticache import ElastiCacheScanner
from .elb import ELBScanner
from .opensearch import OpenSearchScanner
from .rds import RDSScanner

ALL_SCANNERS: list[type[BaseScanner]] = [
    RDSScanner,
    ElastiCacheScanner,
    EKSScanner,
    EC2Scanner,
    EBSScanner,
    ECSScanner,
    ELBScanner,
    OpenSearchScanner,
]

__all__ = [
    "BaseScanner",
    "RDSScanner",
    "ElastiCacheScanner",
    "EKSScanner",
    "EC2Scanner",
    "EBSScanner",
    "ECSScanner",
    "ELBScanner",
    "OpenSearchScanner",
    "ALL_SCANNERS",
]
