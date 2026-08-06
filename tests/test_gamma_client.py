import httpx
import respx

from polymkt.clients.gamma_client import GammaClient

MARKETS_PAGE = [
    {
        "id": "703257",
        "slug": "will-the-us-confirm-that-aliens-exist-before-2027",
        "question": "Will the US confirm that aliens exist before 2027?",
        "conditionId": "0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75",
        "category": "Culture",
        "active": True,
        "clobTokenIds": '["1075058827","7305630249"]',
    }
]


@respx.mock
def test_get_active_markets_queries_active_non_closed_markets():
    route = respx.get("https://gamma-api.polymarket.com/markets").mock(
        return_value=httpx.Response(200, json=MARKETS_PAGE)
    )

    client = GammaClient(base_url="https://gamma-api.polymarket.com")
    markets = client.get_active_markets(limit=100, offset=0)

    assert route.called
    request_params = route.calls.last.request.url.params
    assert request_params["active"] == "true"
    assert request_params["closed"] == "false"
    assert request_params["limit"] == "100"
    assert markets == MARKETS_PAGE


@respx.mock
def test_get_active_markets_raises_on_http_error():
    respx.get("https://gamma-api.polymarket.com/markets").mock(
        return_value=httpx.Response(500)
    )

    client = GammaClient(base_url="https://gamma-api.polymarket.com")

    try:
        client.get_active_markets()
        raise AssertionError("expected HTTPStatusError")
    except httpx.HTTPStatusError:
        pass
