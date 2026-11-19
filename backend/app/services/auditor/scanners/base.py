from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any

import boto3


class BaseScanner(ABC):
    """Base class for all AWS service scanners."""

    SERVICE: str = ""
    REQUIRED_PERMISSIONS: list[str] = []

    def __init__(self, session: boto3.Session, region: str, logger: logging.Logger | None = None) -> None:
        self._session = session
        self._region = region
        self.logger = logger or logging.getLogger(f"scanner.{self.SERVICE}")

    @abstractmethod
    async def scan(self) -> list[dict]:
        ...

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _client(self, service_name: str) -> Any:
        return self._session.client(service_name, region_name=self._region)

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    async def _paginate(
        self,
        client: Any,
        method: str,
        result_key: str,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> list[dict]:
        items: list[dict] = []
        paginator = client.get_paginator(method)
        retry = 0
        page_iter = paginator.paginate(**kwargs).__iter__()

        while True:
            try:
                page = await self._run_sync(next, page_iter, _SENTINEL)
                if page is _SENTINEL:
                    break
                items.extend(page.get(result_key, []))
                retry = 0
            except StopIteration:
                break
            except client.exceptions.ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code == "Throttling" and retry < max_retries:
                    retry += 1
                    wait = min(2**retry + random.uniform(0, 1), 30)
                    self.logger.warning("Throttled on %s, retry %d after %.1fs", method, retry, wait)
                    await asyncio.sleep(wait)
                    page_iter = paginator.paginate(**kwargs).__iter__()
                    # skip already-collected pages – conservative: re-collect
                    items.clear()
                    continue
                raise
        return items

    async def _call(
        self,
        client: Any,
        method: str,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> dict:
        retry = 0
        while True:
            try:
                return await self._run_sync(getattr(client, method), **kwargs)
            except client.exceptions.ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code == "Throttling" and retry < max_retries:
                    retry += 1
                    wait = min(2**retry + random.uniform(0, 1), 30)
                    self.logger.warning("Throttled on %s, retry %d after %.1fs", method, retry, wait)
                    await asyncio.sleep(wait)
                    continue
                raise

    async def _safe_scan(self) -> list[dict]:
        try:
            return await self.scan()
        except Exception as exc:
            err_code = ""
            if hasattr(exc, "response"):
                err_code = exc.response.get("Error", {}).get("Code", "")  # type: ignore[union-attr]
            if err_code in (
                "AccessDenied",
                "AccessDeniedException",
                "UnauthorizedAccess",
                "AuthorizationError",
            ):
                self.logger.warning(
                    "Access denied for %s in %s – skipping (missing permissions)",
                    self.SERVICE,
                    self._region,
                )
                return []
            self.logger.exception("Scanner %s failed in %s", self.SERVICE, self._region)
            return []

    def _get_tags_dict(self, tag_list: list[dict] | None) -> dict[str, str]:
        if not tag_list:
            return {}
        return {t.get("Key", t.get("key", "")): t.get("Value", t.get("value", "")) for t in tag_list}

    def _extract_name(self, tags: dict[str, str], fallback: str | None = None) -> str | None:
        return tags.get("Name") or tags.get("name") or fallback

    def _resource(
        self,
        *,
        arn: str,
        resource_type: str,
        az: str | None = None,
        name: str | None = None,
        configuration: dict | None = None,
        multi_az: bool = False,
        tags: dict[str, str] | None = None,
        **extra: Any,
    ) -> dict:
        return {
            "arn": arn,
            "resource_type": resource_type,
            "service": self.SERVICE,
            "region": self._region,
            "az": az,
            "name": name,
            "configuration": configuration or {},
            "multi_az": multi_az,
            "tags": tags or {},
            **extra,
        }


_SENTINEL = object()
