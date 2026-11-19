from __future__ import annotations

from collections import defaultdict

from .base import BaseScanner


class EC2Scanner(BaseScanner):
    SERVICE = "ec2"

    async def scan(self) -> list[dict]:
        ec2 = self._client("ec2")
        asg_client = self._client("autoscaling")
        resources: list[dict] = []

        asgs = await self._paginate(
            asg_client, "describe_auto_scaling_groups", "AutoScalingGroups",
        )
        asg_instance_ids: set[str] = set()
        for asg in asgs:
            asg_name = asg.get("AutoScalingGroupName", "")
            asg_arn = asg.get("AutoScalingGroupARN", "")
            azs = asg.get("AvailabilityZones", [])
            multi_az = len(azs) > 1

            for inst in asg.get("Instances", []):
                iid = inst.get("InstanceId")
                if iid:
                    asg_instance_ids.add(iid)

            instance_type = ""
            lt = asg.get("LaunchTemplate") or {}
            lc_name = asg.get("LaunchConfigurationName", "")
            mixed = asg.get("MixedInstancesPolicy") or {}
            if lt.get("LaunchTemplateId"):
                instance_type = f"lt:{lt['LaunchTemplateId']}"
            elif mixed:
                overrides = (
                    mixed.get("LaunchTemplate", {})
                    .get("Overrides", [])
                )
                instance_type = ",".join(o.get("InstanceType", "") for o in overrides[:5] if o.get("InstanceType"))
            elif lc_name:
                instance_type = f"lc:{lc_name}"

            tags = self._get_tags_dict(asg.get("Tags"))
            name = self._extract_name(tags, asg_name)

            resources.append(self._resource(
                arn=asg_arn,
                resource_type="auto_scaling_group",
                az=None,
                name=name,
                configuration={
                    "asg_name": asg_name,
                    "availability_zones": sorted(azs),
                    "min_size": asg.get("MinSize"),
                    "max_size": asg.get("MaxSize"),
                    "desired_capacity": asg.get("DesiredCapacity"),
                    "instance_type": instance_type,
                    "launch_template": lt,
                    "launch_configuration": lc_name or None,
                    "health_check_type": asg.get("HealthCheckType"),
                    "target_group_arns": asg.get("TargetGroupARNs", []),
                    "instance_count": len(asg.get("Instances", [])),
                    "status": "active",
                },
                multi_az=multi_az,
                tags=tags,
            ))

        reservations = await self._paginate(
            ec2, "describe_instances", "Reservations",
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}],
        )
        role_groups: dict[str, list[dict]] = defaultdict(list)
        standalone: list[dict] = []

        for reservation in reservations:
            for inst in reservation.get("Instances", []):
                iid = inst.get("InstanceId", "")
                if iid in asg_instance_ids:
                    continue
                standalone.append(inst)
                tags = self._get_tags_dict(inst.get("Tags"))
                role_key = tags.get("role") or tags.get("Role") or tags.get("aws:cloudformation:stack-name", "")
                if role_key:
                    role_groups[role_key].append(inst)

        cross_az_roles: set[str] = set()
        for role_key, instances in role_groups.items():
            azs = {i.get("Placement", {}).get("AvailabilityZone") for i in instances}
            azs.discard(None)
            if len(azs) > 1:
                cross_az_roles.add(role_key)

        account_id = self._session.client("sts", region_name=self._region).get_caller_identity()["Account"]

        for inst in standalone:
            iid = inst["InstanceId"]
            az = inst.get("Placement", {}).get("AvailabilityZone", "")
            tags = self._get_tags_dict(inst.get("Tags"))
            name = self._extract_name(tags, iid)
            role_key = tags.get("role") or tags.get("Role") or tags.get("aws:cloudformation:stack-name", "")
            multi_az = role_key in cross_az_roles

            arn = f"arn:aws:ec2:{self._region}:{account_id}:instance/{iid}"

            resources.append(self._resource(
                arn=arn,
                resource_type="instance",
                az=az,
                name=name,
                configuration={
                    "instance_id": iid,
                    "instance_type": inst.get("InstanceType"),
                    "availability_zone": az,
                    "state": inst.get("State", {}).get("Name"),
                    "vpc_id": inst.get("VpcId"),
                    "subnet_id": inst.get("SubnetId"),
                    "private_ip": inst.get("PrivateIpAddress"),
                    "iam_instance_profile": (inst.get("IamInstanceProfile") or {}).get("Arn"),
                    "platform": inst.get("PlatformDetails"),
                    "launch_time": str(inst.get("LaunchTime", "")),
                    "cross_az_role": role_key if multi_az else None,
                },
                multi_az=multi_az,
                tags=tags,
            ))

        return resources
