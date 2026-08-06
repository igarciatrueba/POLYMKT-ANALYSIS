import httpx


class GammaClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=10.0)

    def get_active_markets(self, limit: int = 100, offset: int = 0) -> list[dict]:
        response = self._client.get(
            "/markets",
            params={"active": "true", "closed": "false", "limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
