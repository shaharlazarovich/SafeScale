from __future__ import annotations

from .base import BaseScanner


class EBSScanner(BaseScanner):
    SERVICE = "ebs"

    async def scan(self) -> list[dict]:
        ec2 = self._client("ec2")
        resources: list[dict] = []

        volumes = await self._paginate(ec2, "describe_volumes", "Volumes")

        multi_az_instance_ids: set[str] = set()
        try:
            rds_client = self._client("rds")
            db_instances = await self._paginate(
                rds_client, "describe_db_instances", "DBInstances",
            )
            for dbi in db_instances:
                if dbi.get("MultiAZ"):
                    for member in dbi.get("DBClusterMembers", []):
                        pass
        except Exception:
            pass

        instance_ids_on_volumes: set[str] = set()
        for vol in volumes:
            for att in vol.get("Attachments", []):
                iid = att.get("InstanceId")
                if iid:
                    instance_ids_on_volumes.add(iid)

        instance_azs: dict[str, str] = {}
        if instance_ids_on_volumes:
            batch_list = list(instance_ids_on_volumes)
            for batch_start in range(0, len(batch_list), 100):
                batch = batch_list[batch_start : batch_start + 100]
                try:
                    resp = await self._call(
                        ec2, "describe_instances", InstanceIds=batch,
                    )
                    for res in resp.get("Reservations", []):
                        for inst in res.get("Instances", []):
                            iid = inst["InstanceId"]
                            instance_azs[iid] = inst.get("Placement", {}).get("AvailabilityZone", "")
                except Exception:
                    pass

        snapshot_schedules: dict[str, bool] = {}
        try:
            dlm_client = self._client("dlm")
            policies_resp = await self._call(
                dlm_client, "get_lifecycle_policies",
                State="ENABLED",
            )
            for policy_summary in policies_resp.get("Policies", []):
                pid = policy_summary.get("PolicyId")
                if not pid:
                    continue
                try:
                    detail_resp = await self._call(
                        dlm_client, "get_lifecycle_policy", PolicyId=pid,
                    )
                    policy = detail_resp.get("Policy", {})
                    target_tags = policy.get("PolicyDetails", {}).get("TargetTags", [])
                    for _tag in target_tags:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

        account_id = ""
        try:
            sts = self._client("sts")
            account_id = (await self._call(sts, "get_caller_identity")).get("Account", "")
        except Exception:
            pass

        for vol in volumes:
            vol_id = vol["VolumeId"]
            az = vol.get("AvailabilityZone", "")
            vol_type = vol.get("VolumeType", "")
            size_gb = vol.get("Size", 0)
            iops = vol.get("Iops")
            throughput = vol.get("Throughput")
            state = vol.get("State", "")

            attachments = vol.get("Attachments", [])
            attached_instances = [a.get("InstanceId") for a in attachments if a.get("InstanceId")]

            attached_to_multi_az = any(iid in multi_az_instance_ids for iid in attached_instances)

            tags = self._get_tags_dict(vol.get("Tags"))
            name = self._extract_name(tags, vol_id)

            has_snapshot_schedule = snapshot_schedules.get(vol_id, False)

            arn = f"arn:aws:ec2:{self._region}:{account_id}:volume/{vol_id}"

            resources.append(self._resource(
                arn=arn,
                resource_type="volume",
                az=az,
                name=name,
                configuration={
                    "volume_id": vol_id,
                    "volume_type": vol_type,
                    "size_gb": size_gb,
                    "iops": iops,
                    "throughput": throughput,
                    "state": state,
                    "availability_zone": az,
                    "encrypted": vol.get("Encrypted", False),
                    "attached_instances": attached_instances,
                    "attachment_count": len(attachments),
                    "multi_az_attachment": attached_to_multi_az,
                    "has_snapshot_schedule": has_snapshot_schedule,
                    "create_time": str(vol.get("CreateTime", "")),
                },
                multi_az=attached_to_multi_az,
                tags=tags,
            ))

        return resources
