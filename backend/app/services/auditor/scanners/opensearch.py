from __future__ import annotations

from .base import BaseScanner


class OpenSearchScanner(BaseScanner):
    SERVICE = "opensearch"

    async def scan(self) -> list[dict]:
        client = self._client("opensearch")
        resources: list[dict] = []

        names_resp = await self._call(client, "list_domain_names")
        domain_names = [d.get("DomainName") for d in names_resp.get("DomainNames", []) if d.get("DomainName")]

        if not domain_names:
            return resources

        for batch_start in range(0, len(domain_names), 5):
            batch = domain_names[batch_start : batch_start + 5]
            domains_resp = await self._call(client, "describe_domains", DomainNames=batch)

            for domain in domains_resp.get("DomainStatusList", []):
                domain_name = domain.get("DomainName", "")
                arn = domain.get("ARN", "")

                cluster_config = domain.get("ClusterConfig", {})
                instance_type = cluster_config.get("InstanceType", "")
                instance_count = cluster_config.get("InstanceCount", 1)
                dedicated_master = cluster_config.get("DedicatedMasterEnabled", False)
                dedicated_master_type = cluster_config.get("DedicatedMasterType")
                dedicated_master_count = cluster_config.get("DedicatedMasterCount")
                warm_enabled = cluster_config.get("WarmEnabled", False)
                warm_type = cluster_config.get("WarmType")
                warm_count = cluster_config.get("WarmCount")

                zone_awareness = cluster_config.get("ZoneAwarenessEnabled", False)
                za_config = cluster_config.get("ZoneAwarenessConfig", {})
                az_count = za_config.get("AvailabilityZoneCount", 1) if zone_awareness else 1

                multi_az = zone_awareness and az_count > 1

                ebs_config = domain.get("EBSOptions", {})
                ebs_enabled = ebs_config.get("EBSEnabled", False)
                volume_type = ebs_config.get("VolumeType") if ebs_enabled else None
                volume_size = ebs_config.get("VolumeSize") if ebs_enabled else None

                vpc_options = domain.get("VPCOptions", {})
                vpc_id = vpc_options.get("VPCId")
                subnet_ids = vpc_options.get("SubnetIds", [])
                security_groups = vpc_options.get("SecurityGroupIds", [])

                encryption_at_rest = domain.get("EncryptionAtRestOptions", {}).get("Enabled", False)
                node_to_node = domain.get("NodeToNodeEncryptionOptions", {}).get("Enabled", False)

                engine_version = domain.get("EngineVersion", "")

                try:
                    tag_resp = await self._call(client, "list_tags", ARN=arn)
                    tags = self._get_tags_dict(tag_resp.get("TagList"))
                except Exception:
                    tags = {}

                name = self._extract_name(tags, domain_name)

                resources.append(self._resource(
                    arn=arn,
                    resource_type="domain",
                    az=None,
                    name=name,
                    configuration={
                        "domain_name": domain_name,
                        "engine_version": engine_version,
                        "instance_type": instance_type,
                        "instance_count": instance_count,
                        "zone_awareness_enabled": zone_awareness,
                        "availability_zone_count": az_count,
                        "dedicated_master_enabled": dedicated_master,
                        "dedicated_master_type": dedicated_master_type,
                        "dedicated_master_count": dedicated_master_count,
                        "warm_enabled": warm_enabled,
                        "warm_type": warm_type,
                        "warm_count": warm_count,
                        "ebs_enabled": ebs_enabled,
                        "ebs_volume_type": volume_type,
                        "ebs_volume_size_gb": volume_size,
                        "vpc_id": vpc_id,
                        "subnet_ids": subnet_ids,
                        "security_group_ids": security_groups,
                        "encryption_at_rest": encryption_at_rest,
                        "node_to_node_encryption": node_to_node,
                        "endpoint": domain.get("Endpoint") or domain.get("Endpoints", {}),
                        "processing": domain.get("Processing", False),
                        "deleted": domain.get("Deleted", False),
                    },
                    multi_az=multi_az,
                    tags=tags,
                ))

        return resources
