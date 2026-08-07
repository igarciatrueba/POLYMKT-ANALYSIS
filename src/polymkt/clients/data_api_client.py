import httpx

POSITIONS_PAGE_SIZE = 500
POSITIONS_MAX_OFFSET = 10_000


class PositionsPaginationError(RuntimeError):
    """Raised when the API cannot provide a complete wallet snapshot."""


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
        positions: list[dict] = []
        position_keys: set[tuple[str, str]] = set()
        offset = 0

        while True:
            response = self._client.get(
                "/positions",
                params={
                    "user": wallet_address,
                    "sizeThreshold": size_threshold,
                    "limit": POSITIONS_PAGE_SIZE,
                    "offset": offset,
                    "sortBy": "TOKENS",
                    "sortDirection": "DESC",
                },
            )
            response.raise_for_status()
            page = response.json()
            page_keys = {
                (position["conditionId"], position["outcome"])
                for position in page
            }
            if len(page_keys) != len(page) or position_keys.intersection(page_keys):
                raise PositionsPaginationError(
                    "Position list changed during pagination for "
                    f"wallet {wallet_address}"
                )
            position_keys.update(page_keys)
            positions.extend(page)

            if len(page) < POSITIONS_PAGE_SIZE:
                return positions
            if offset >= POSITIONS_MAX_OFFSET:
                raise PositionsPaginationError(
                    "Position snapshot exceeds the API pagination limit for "
                    f"wallet {wallet_address}"
                )
            offset += POSITIONS_PAGE_SIZE

    def close(self) -> None:
        self._client.close()
