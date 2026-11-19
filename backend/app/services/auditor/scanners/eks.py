from __future__ import annotations

from .base import BaseScanner


class EKSScanner(BaseScanner):
    SERVICE = "eks"

    async def scan(self) -> list[dict]:
        eks_client = self._client("eks")
        ec2_client = self._client("ec2")
        resources: list[dict] = []

        cluster_names = await self._paginate(eks_client, "list_clusters", "clusters")

        subnet_az_cache: dict[str, str] = {}

        async def _resolve_subnet_azs(subnet_ids: list[str]) -> dict[str, str]:
            unknown = [s for s in subnet_ids if s not in subnet_az_cache]
            if unknown:
                for batch_start in range(0, len(unknown), 50):
                    batch = unknown[batch_start : batch_start + 50]
                    resp = await self._call(ec2_client, "describe_subnets", SubnetIds=batch)
                    for sn in resp.get("Subnets", []):
                        subnet_az_cache[sn["SubnetId"]] = sn.get("AvailabilityZone", "")
            return {sid: subnet_az_cache.get(sid, "") for sid in subnet_ids}

        for cluster_name in cluster_names:
            cluster_resp = await self._call(eks_client, "describe_cluster", name=cluster_name)
            cluster = cluster_resp.get("cluster", {})
            cluster_arn = cluster.get("arn", "")

            vpc_config = cluster.get("resourcesVpcConfig", {})
            cluster_subnets = vpc_config.get("subnetIds", [])
            subnet_azs = await _resolve_subnet_azs(cluster_subnets)
            cluster_azs = sorted({az for az in subnet_azs.values() if az})
            cluster_multi_az = len(cluster_azs) > 1

            tags = cluster.get("tags", {})
            name = self._extract_name(tags, cluster_name)

            resources.append(self._resource(
                arn=cluster_arn,
                resource_type="cluster",
                az=None,
                name=name,
                configuration={
                    "cluster_name": cluster_name,
                    "status": cluster.get("status"),
                    "version": cluster.get("version"),
                    "platform_version": cluster.get("platformVersion"),
                    "vpc_id": vpc_config.get("vpcId"),
                    "subnet_ids": cluster_subnets,
                    "availability_zones": cluster_azs,
                    "endpoint": cluster.get("endpoint"),
                    "role_arn": cluster.get("roleArn"),
                },
                multi_az=cluster_multi_az,
                tags=tags,
            ))

            ng_names = await self._paginate(
                eks_client, "list_nodegroups", "nodegroups", clusterName=cluster_name,
            )
            for ng_name in ng_names:
                ng_resp = await self._call(
                    eks_client, "describe_nodegroup",
                    clusterName=cluster_name, nodegroupName=ng_name,
                )
                ng = ng_resp.get("nodegroup", {})
                ng_arn = ng.get("nodegroupArn", "")
                ng_subnets = ng.get("subnets", [])
                ng_subnet_azs = await _resolve_subnet_azs(ng_subnets)
                ng_azs = sorted({az for az in ng_subnet_azs.values() if az})
                ng_multi_az = len(ng_azs) > 1

                scaling = ng.get("scalingConfig", {})
                instance_types = ng.get("instanceTypes", [])
                ng_tags = ng.get("tags", {})
                ng_name_tag = self._extract_name(ng_tags, ng_name)

                resources.append(self._resource(
                    arn=ng_arn,
                    resource_type="nodegroup",
                    az=None,
                    name=ng_name_tag,
                    configuration={
                        "nodegroup_name": ng_name,
                        "cluster_name": cluster_name,
                        "status": ng.get("status"),
                        "instance_types": instance_types,
                        "ami_type": ng.get("amiType"),
                        "capacity_type": ng.get("capacityType"),
                        "disk_size": ng.get("diskSize"),
                        "scaling_config": {
                            "min_size": scaling.get("minSize"),
                            "max_size": scaling.get("maxSize"),
                            "desired_size": scaling.get("desiredSize"),
                        },
                        "subnet_ids": ng_subnets,
                        "availability_zones": ng_azs,
                        "release_version": ng.get("releaseVersion"),
                    },
                    multi_az=ng_multi_az,
                    tags=ng_tags,
                ))

        return resources
