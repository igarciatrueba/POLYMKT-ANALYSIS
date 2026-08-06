import httpx


class ClobClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=10.0)

    def get_order_books(self, token_ids: list[str]) -> list[dict]:
        response = self._client.post("/books", json=token_ids)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
