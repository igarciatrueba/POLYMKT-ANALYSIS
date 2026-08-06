import json

import httpx
import respx

from polymkt.clients.clob_client import ClobClient

BOOKS_RESPONSE = [
    {
        "asset_id": "1075058827",
        "bids": [{"price": "0.42", "size": "100"}],
        "asks": [{"price": "0.45", "size": "80"}],
    }
]


@respx.mock
def test_get_order_books_posts_token_ids_and_returns_books():
    route = respx.post("https://clob.polymarket.com/books").mock(
        return_value=httpx.Response(200, json=BOOKS_RESPONSE)
    )

    client = ClobClient(base_url="https://clob.polymarket.com")
    books = client.get_order_books(["1075058827"])

    assert route.called
    assert json.loads(route.calls.last.request.content) == ["1075058827"]
    assert books == BOOKS_RESPONSE


@respx.mock
def test_get_order_books_raises_on_http_error():
    respx.post("https://clob.polymarket.com/books").mock(return_value=httpx.Response(500))

    client = ClobClient(base_url="https://clob.polymarket.com")

    try:
        client.get_order_books(["111"])
        raise AssertionError("expected HTTPStatusError")
    except httpx.HTTPStatusError:
        pass
