from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.settings import settings


class OsrsApiError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    # Required by OSRS wiki acceptable use policy; defaults like python-requests/curl are blocked.
    return {"User-Agent": settings.osrs_user_agent}


class OsrsPricesClient:
    def __init__(self) -> None:
        self._base = str(settings.osrs_base_url).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base, headers=_headers(), timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, OsrsApiError)),
    )
    async def get_mapping(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/mapping")
        if resp.status_code != 200:
            raise OsrsApiError(f"mapping failed: HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not isinstance(data, list):
            raise OsrsApiError("mapping response not a list")
        return data

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, OsrsApiError)),
    )
    async def get_5m_bucket(self, timestamp: int) -> dict[str, Any]:
        resp = await self._client.get("/5m", params={"timestamp": timestamp})
        if resp.status_code != 200:
            raise OsrsApiError(f"5m failed: HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not isinstance(data, dict) or "data" not in data:
            raise OsrsApiError("5m response missing data field")
        return data

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, OsrsApiError)),
    )
    async def get_timeseries(self, item_id: int, timestep: str) -> dict[str, Any]:
        resp = await self._client.get("/timeseries", params={"id": item_id, "timestep": timestep})
        if resp.status_code != 200:
            raise OsrsApiError(f"timeseries failed: HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not isinstance(data, dict) or "data" not in data:
            raise OsrsApiError("timeseries response missing data field")
        return data


