from __future__ import annotations

from .base import BaseScanner


class RDSScanner(BaseScanner):
    SERVICE = "rds"

    async def scan(self) -> list[dict]:
        client = self._client("rds")
        resources: list[dict] = []

        instances = await self._paginate(client, "describe_db_instances", "DBInstances")
        for inst in instances:
            arn = inst["DBInstanceArn"]
            engine = inst.get("Engine", "")
            is_aurora = engine.startswith("aurora")
            tags = self._get_tags_dict(inst.get("TagList"))
            name = self._extract_name(tags, inst.get("DBInstanceIdentifier"))
            multi_az = inst.get("MultiAZ", False)

            az = inst.get("AvailabilityZone")
            secondary_az = inst.get("SecondaryAvailabilityZone")

            resources.append(self._resource(
                arn=arn,
                resource_type="aurora_instance" if is_aurora else "db_instance",
                az=az,
                name=name,
                configuration={
                    "db_instance_identifier": inst.get("DBInstanceIdentifier"),
                    "db_instance_class": inst.get("DBInstanceClass"),
                    "engine": engine,
                    "engine_version": inst.get("EngineVersion"),
                    "multi_az": multi_az,
                    "availability_zone": az,
                    "secondary_availability_zone": secondary_az,
                    "storage_type": inst.get("StorageType"),
                    "allocated_storage": inst.get("AllocatedStorage"),
                    "db_instance_status": inst.get("DBInstanceStatus"),
                    "vpc_id": (inst.get("DBSubnetGroup") or {}).get("VpcId"),
                    "db_subnet_group": (inst.get("DBSubnetGroup") or {}).get("DBSubnetGroupName"),
                    "db_cluster_identifier": inst.get("DBClusterIdentifier"),
                    "iops": inst.get("Iops"),
                    "storage_encrypted": inst.get("StorageEncrypted"),
                    "publicly_accessible": inst.get("PubliclyAccessible"),
                },
                multi_az=multi_az,
                tags=tags,
            ))

        clusters = await self._paginate(client, "describe_db_clusters", "DBClusters")
        for cluster in clusters:
            arn = cluster["DBClusterArn"]
            engine = cluster.get("Engine", "")
            tags = self._get_tags_dict(cluster.get("TagList"))
            name = self._extract_name(tags, cluster.get("DBClusterIdentifier"))

            member_azs = {m.get("DBClusterAvailabilityZone") for m in cluster.get("DBClusterMembers", []) if m.get("DBClusterAvailabilityZone")}
            multi_az = cluster.get("MultiAZ", False) or len(member_azs) > 1

            resources.append(self._resource(
                arn=arn,
                resource_type="db_cluster",
                az=None,
                name=name,
                configuration={
                    "db_cluster_identifier": cluster.get("DBClusterIdentifier"),
                    "engine": engine,
                    "engine_version": cluster.get("EngineVersion"),
                    "engine_mode": cluster.get("EngineMode"),
                    "multi_az": multi_az,
                    "availability_zones": cluster.get("AvailabilityZones", []),
                    "member_count": len(cluster.get("DBClusterMembers", [])),
                    "member_azs": sorted(member_azs),
                    "status": cluster.get("Status"),
                    "storage_encrypted": cluster.get("StorageEncrypted"),
                    "allocated_storage": cluster.get("AllocatedStorage"),
                    "serverless_v2_scaling": cluster.get("ServerlessV2ScalingConfiguration"),
                },
                multi_az=multi_az,
                tags=tags,
            ))

        return resources
