import httpx
import respx

from polymkt.clients.data_api_client import DataApiClient

LEADERBOARD_PAGE = [
    {"rank": "1", "proxyWallet": "0x111", "userName": "whale1", "vol": 2000000.0, "pnl": 500000.0}
]

POSITIONS_PAGE = [
    {
        "proxyWallet": "0x111",
        "conditionId": "0xabc",
        "outcome": "Yes",
        "size": 1200.0,
        "currentValue": 540.0,
    }
]


@respx.mock
def test_get_leaderboard_queries_expected_params():
    route = respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
        return_value=httpx.Response(200, json=LEADERBOARD_PAGE)
    )

    client = DataApiClient(base_url="https://data-api.polymarket.com")
    traders = client.get_leaderboard(category="OVERALL", time_period="ALL", limit=50, offset=0)

    assert route.called
    params = route.calls.last.request.url.params
    assert params["category"] == "OVERALL"
    assert params["timePeriod"] == "ALL"
    assert params["orderBy"] == "PNL"
    assert traders == LEADERBOARD_PAGE


@respx.mock
def test_get_positions_queries_by_user():
    route = respx.get("https://data-api.polymarket.com/positions").mock(
        return_value=httpx.Response(200, json=POSITIONS_PAGE)
    )

    client = DataApiClient(base_url="https://data-api.polymarket.com")
    positions = client.get_positions("0x111")

    assert route.called
    assert route.calls.last.request.url.params["user"] == "0x111"
    assert positions == POSITIONS_PAGE
