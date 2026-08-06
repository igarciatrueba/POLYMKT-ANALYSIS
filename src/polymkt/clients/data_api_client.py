import httpx


class DataApiClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=10.0)

    def get_leaderboard(
        self,
        *,
        category: str = "OVERALL",
        time_period: str = "ALL",
        order_by: str = "PNL",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        response = self._client.get(
            "/v1/leaderboard",
            params={
                "category": category,
                "timePeriod": time_period,
                "orderBy": order_by,
                "limit": limit,
                "offset": offset,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_positions(self, wallet_address: str, *, size_threshold: float = 1.0) -> list[dict]:
        response = self._client.get(
            "/positions",
            params={"user": wallet_address, "sizeThreshold": size_threshold, "limit": 500},
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
