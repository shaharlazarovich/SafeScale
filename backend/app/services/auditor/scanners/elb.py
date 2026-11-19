from __future__ import annotations

from .base import BaseScanner


class ELBScanner(BaseScanner):
    SERVICE = "elb"

    async def scan(self) -> list[dict]:
        elbv2 = self._client("elbv2")
        ec2_client = self._client("ec2")
        resources: list[dict] = []

        lbs = await self._paginate(elbv2, "describe_load_balancers", "LoadBalancers")

        subnet_az_cache: dict[str, str] = {}

        for lb in lbs:
            lb_arn = lb.get("LoadBalancerArn", "")
            lb_name = lb.get("LoadBalancerName", "")
            lb_type = lb.get("Type", "")
            scheme = lb.get("Scheme", "")
            state = lb.get("State", {}).get("Code", "")
            vpc_id = lb.get("VpcId", "")

            az_info = lb.get("AvailabilityZones", [])
            lb_azs = sorted({z.get("ZoneName", "") for z in az_info} - {""})
            lb_subnets = [z.get("SubnetId", "") for z in az_info if z.get("SubnetId")]
            multi_az = len(lb_azs) > 1

            try:
                tag_resp = await self._call(
                    elbv2, "describe_tags", ResourceArns=[lb_arn],
                )
                tag_descriptions = tag_resp.get("TagDescriptions", [])
                raw_tags = tag_descriptions[0].get("Tags", []) if tag_descriptions else []
                tags = self._get_tags_dict(raw_tags)
            except Exception:
                tags = {}

            name = self._extract_name(tags, lb_name)

            tg_arns: list[str] = []
            target_groups: list[dict] = []
            try:
                tgs = await self._paginate(
                    elbv2, "describe_target_groups", "TargetGroups",
                    LoadBalancerArn=lb_arn,
                )
                for tg in tgs:
                    tg_arn = tg.get("TargetGroupArn", "")
                    tg_arns.append(tg_arn)

                    targets: list[dict] = []
                    target_azs: set[str] = set()
                    try:
                        health_resp = await self._call(
                            elbv2, "describe_target_health",
                            TargetGroupArn=tg_arn,
                        )
                        for thd in health_resp.get("TargetHealthDescriptions", []):
                            target = thd.get("Target", {})
                            target_id = target.get("Id", "")
                            target_az = target.get("AvailabilityZone")
                            health_state = thd.get("TargetHealth", {}).get("State", "")
                            targets.append({
                                "id": target_id,
                                "port": target.get("Port"),
                                "az": target_az,
                                "health": health_state,
                            })
                            if target_az and target_az != "all":
                                target_azs.add(target_az)
                    except Exception:
                        pass

                    target_groups.append({
                        "arn": tg_arn,
                        "name": tg.get("TargetGroupName", ""),
                        "protocol": tg.get("Protocol"),
                        "port": tg.get("Port"),
                        "target_type": tg.get("TargetType"),
                        "health_check_protocol": tg.get("HealthCheckProtocol"),
                        "health_check_path": tg.get("HealthCheckPath"),
                        "healthy_targets": sum(1 for t in targets if t["health"] == "healthy"),
                        "total_targets": len(targets),
                        "target_azs": sorted(target_azs),
                        "cross_az_targets": len(target_azs) > 1,
                    })
            except Exception:
                pass

            cross_az_data_transfer = multi_az and any(
                tg.get("cross_az_targets") for tg in target_groups
            )

            listeners: list[dict] = []
            try:
                listener_resp = await self._paginate(
                    elbv2, "describe_listeners", "Listeners",
                    LoadBalancerArn=lb_arn,
                )
                for lsnr in listener_resp:
                    listeners.append({
                        "port": lsnr.get("Port"),
                        "protocol": lsnr.get("Protocol"),
                    })
            except Exception:
                pass

            resources.append(self._resource(
                arn=lb_arn,
                resource_type=lb_type.lower() if lb_type else "load_balancer",
                az=None,
                name=name,
                configuration={
                    "load_balancer_name": lb_name,
                    "type": lb_type,
                    "scheme": scheme,
                    "state": state,
                    "vpc_id": vpc_id,
                    "availability_zones": lb_azs,
                    "subnets": lb_subnets,
                    "dns_name": lb.get("DNSName"),
                    "ip_address_type": lb.get("IpAddressType"),
                    "listeners": listeners,
                    "target_groups": target_groups,
                    "target_group_count": len(target_groups),
                    "cross_az_data_transfer": cross_az_data_transfer,
                },
                multi_az=multi_az,
                tags=tags,
            ))

        return resources
