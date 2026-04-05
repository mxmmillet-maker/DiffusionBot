from typing import Any

import httpx


class APIPosterMixin:
    """Mixin pour les plateformes avec API REST."""

    _client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _get(self, url: str, token: str | None = None, **kwargs) -> httpx.Response:
        client = await self._get_client()
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await client.get(url, headers=headers, **kwargs)

    async def _post(
        self, url: str, token: str | None = None, **kwargs: Any
    ) -> httpx.Response:
        client = await self._get_client()
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await client.post(url, headers=headers, **kwargs)

    async def cleanup(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
