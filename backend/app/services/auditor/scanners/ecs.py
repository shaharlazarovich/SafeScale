from __future__ import annotations

from .base import BaseScanner


class ECSScanner(BaseScanner):
    SERVICE = "ecs"

    async def scan(self) -> list[dict]:
        client = self._client("ecs")
        ec2_client = self._client("ec2")
        resources: list[dict] = []

        cluster_arns = await self._paginate(client, "list_clusters", "clusterArns")
        if not cluster_arns:
            return resources

        for batch_start in range(0, len(cluster_arns), 10):
            batch = cluster_arns[batch_start : batch_start + 10]
            clusters_resp = await self._call(client, "describe_clusters", clusters=batch, include=["TAGS"])

            for cluster in clusters_resp.get("clusters", []):
                cluster_arn = cluster["clusterArn"]
                cluster_name = cluster.get("clusterName", "")
                tags = self._get_tags_dict(cluster.get("tags"))
                name = self._extract_name(tags, cluster_name)

                resources.append(self._resource(
                    arn=cluster_arn,
                    resource_type="cluster",
                    az=None,
                    name=name,
                    configuration={
                        "cluster_name": cluster_name,
                        "status": cluster.get("status"),
                        "active_services_count": cluster.get("activeServicesCount"),
                        "running_tasks_count": cluster.get("runningTasksCount"),
                        "pending_tasks_count": cluster.get("pendingTasksCount"),
                        "registered_container_instances": cluster.get("registeredContainerInstancesCount"),
                    },
                    multi_az=False,
                    tags=tags,
                ))

                service_arns = await self._paginate(
                    client, "list_services", "serviceArns", cluster=cluster_arn,
                )
                if not service_arns:
                    continue

                subnet_az_cache: dict[str, str] = {}

                for svc_batch_start in range(0, len(service_arns), 10):
                    svc_batch = service_arns[svc_batch_start : svc_batch_start + 10]
                    svc_resp = await self._call(
                        client, "describe_services",
                        cluster=cluster_arn, services=svc_batch, include=["TAGS"],
                    )

                    for svc in svc_resp.get("services", []):
                        svc_arn = svc["serviceArn"]
                        svc_name = svc.get("serviceName", "")
                        launch_type = svc.get("launchType", "")
                        desired = svc.get("desiredCount", 0)

                        net_config = svc.get("networkConfiguration", {}).get("awsvpcConfiguration", {})
                        subnets = net_config.get("subnets", [])

                        unknown_subnets = [s for s in subnets if s not in subnet_az_cache]
                        if unknown_subnets:
                            for sub_batch_start in range(0, len(unknown_subnets), 50):
                                sub_batch = unknown_subnets[sub_batch_start : sub_batch_start + 50]
                                try:
                                    sn_resp = await self._call(ec2_client, "describe_subnets", SubnetIds=sub_batch)
                                    for sn in sn_resp.get("Subnets", []):
                                        subnet_az_cache[sn["SubnetId"]] = sn.get("AvailabilityZone", "")
                                except Exception:
                                    pass

                        svc_azs = sorted({subnet_az_cache.get(s, "") for s in subnets} - {""})
                        multi_az = len(svc_azs) > 1

                        placement = svc.get("placementStrategy", [])
                        placement_constraints = svc.get("placementConstraints", [])

                        svc_tags = self._get_tags_dict(svc.get("tags"))
                        svc_display = self._extract_name(svc_tags, svc_name)

                        task_def = svc.get("taskDefinition", "")
                        cpu = None
                        memory = None
                        if task_def:
                            try:
                                td_resp = await self._call(client, "describe_task_definition", taskDefinition=task_def)
                                td = td_resp.get("taskDefinition", {})
                                cpu = td.get("cpu")
                                memory = td.get("memory")
                            except Exception:
                                pass

                        resources.append(self._resource(
                            arn=svc_arn,
                            resource_type="service",
                            az=None,
                            name=svc_display,
                            configuration={
                                "service_name": svc_name,
                                "cluster_name": cluster_name,
                                "cluster_arn": cluster_arn,
                                "launch_type": launch_type,
                                "platform_version": svc.get("platformVersion"),
                                "desired_count": desired,
                                "running_count": svc.get("runningCount"),
                                "status": svc.get("status"),
                                "subnets": subnets,
                                "availability_zones": svc_azs,
                                "task_definition": task_def,
                                "cpu": cpu,
                                "memory": memory,
                                "placement_strategy": placement,
                                "placement_constraints": placement_constraints,
                                "scheduling_strategy": svc.get("schedulingStrategy"),
                                "load_balancers": svc.get("loadBalancers", []),
                            },
                            multi_az=multi_az,
                            tags=svc_tags,
                        ))

        return resources
