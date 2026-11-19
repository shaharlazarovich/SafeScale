from __future__ import annotations

from .base import BaseScanner


class ElastiCacheScanner(BaseScanner):
    SERVICE = "elasticache"

    async def scan(self) -> list[dict]:
        client = self._client("elasticache")
        resources: list[dict] = []

        repl_groups = await self._paginate(
            client, "describe_replication_groups", "ReplicationGroups",
        )
        repl_group_ids: set[str] = set()
        for rg in repl_groups:
            rg_id = rg.get("ReplicationGroupId", "")
            repl_group_ids.add(rg_id)
            arn = rg.get("ARN", "")

            automatic_failover = rg.get("AutomaticFailover", "disabled")
            multi_az_enabled = rg.get("MultiAZEnabled", False)
            multi_az = multi_az_enabled or automatic_failover == "enabled"

            node_groups = rg.get("NodeGroups", [])
            all_azs: set[str] = set()
            total_nodes = 0
            node_type = ""
            for ng in node_groups:
                for member in ng.get("NodeGroupMembers", []):
                    az = member.get("PreferredAvailabilityZone")
                    if az:
                        all_azs.add(az)
                    total_nodes += 1
            if not multi_az and len(all_azs) > 1:
                multi_az = True

            cache_clusters = rg.get("MemberClusters", [])
            if not node_type:
                node_type = rg.get("CacheNodeType", "")

            try:
                tag_resp = await self._call(client, "list_tags_for_resource", ResourceName=arn)
                tags = self._get_tags_dict(tag_resp.get("TagList"))
            except Exception:
                tags = {}

            name = self._extract_name(tags, rg_id)

            resources.append(self._resource(
                arn=arn,
                resource_type="replication_group",
                az=None,
                name=name,
                configuration={
                    "replication_group_id": rg_id,
                    "description": rg.get("Description"),
                    "status": rg.get("Status"),
                    "node_type": node_type,
                    "engine": "redis",
                    "automatic_failover": automatic_failover,
                    "multi_az_enabled": multi_az_enabled,
                    "cluster_enabled": rg.get("ClusterEnabled", False),
                    "num_node_groups": len(node_groups),
                    "total_nodes": total_nodes,
                    "member_clusters": cache_clusters,
                    "availability_zones": sorted(all_azs),
                    "at_rest_encryption": rg.get("AtRestEncryptionEnabled"),
                    "transit_encryption": rg.get("TransitEncryptionEnabled"),
                },
                multi_az=multi_az,
                tags=tags,
            ))

        standalone = await self._paginate(
            client, "describe_cache_clusters", "CacheClusters",
            ShowCacheNodeInfo=True,
        )
        for cc in standalone:
            cluster_id = cc.get("CacheClusterId", "")
            if cc.get("ReplicationGroupId") in repl_group_ids:
                continue

            arn = cc.get("ARN", "")
            engine = cc.get("Engine", "memcached")
            az = cc.get("PreferredAvailabilityZone")
            node_type = cc.get("CacheNodeType", "")
            num_nodes = cc.get("NumCacheNodes", 1)

            node_azs: set[str] = set()
            for node in cc.get("CacheNodes", []):
                node_az = node.get("CustomerAvailabilityZone")
                if node_az:
                    node_azs.add(node_az)
            multi_az = len(node_azs) > 1

            try:
                tag_resp = await self._call(client, "list_tags_for_resource", ResourceName=arn)
                tags = self._get_tags_dict(tag_resp.get("TagList"))
            except Exception:
                tags = {}

            name = self._extract_name(tags, cluster_id)

            resources.append(self._resource(
                arn=arn,
                resource_type="cache_cluster",
                az=az,
                name=name,
                configuration={
                    "cache_cluster_id": cluster_id,
                    "engine": engine,
                    "engine_version": cc.get("EngineVersion"),
                    "node_type": node_type,
                    "num_cache_nodes": num_nodes,
                    "status": cc.get("CacheClusterStatus"),
                    "preferred_az": az,
                    "node_azs": sorted(node_azs),
                    "az_mode": cc.get("AZMode"),
                },
                multi_az=multi_az,
                tags=tags,
            ))

        return resources
