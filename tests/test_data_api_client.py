import httpx
import pytest
import respx

from polymkt.clients.data_api_client import DataApiClient, PositionsPaginationError

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


@respx.mock
def test_get_positions_fetches_every_page():
    first_page = [
        {
            **POSITIONS_PAGE[0],
            "conditionId": f"0x{index:064x}",
            "asset": str(index),
        }
        for index in range(500)
    ]
    last_page = [
        {
            **POSITIONS_PAGE[0],
            "conditionId": f"0x{500:064x}",
            "asset": "500",
        }
    ]

    def respond(request):
        offset = int(request.url.params["offset"])
        page = first_page if offset == 0 else last_page
        return httpx.Response(200, json=page)

    route = respx.get("https://data-api.polymarket.com/positions").mock(
        side_effect=respond
    )
    client = DataApiClient(base_url="https://data-api.polymarket.com")

    positions = client.get_positions("0x111")

    assert len(positions) == 501
    assert [int(call.request.url.params["offset"]) for call in route.calls] == [0, 500]
    assert all(call.request.url.params["sortBy"] == "TOKENS" for call in route.calls)
    assert all(call.request.url.params["sortDirection"] == "DESC" for call in route.calls)


@respx.mock
def test_get_positions_rejects_a_snapshot_larger_than_the_api_offset_limit(monkeypatch):
    monkeypatch.setattr("polymkt.clients.data_api_client.POSITIONS_MAX_OFFSET", 500)
    full_page = [
        {**POSITIONS_PAGE[0], "asset": str(index)}
        for index in range(500)
    ]
    respx.get("https://data-api.polymarket.com/positions").mock(
        return_value=httpx.Response(200, json=full_page)
    )
    client = DataApiClient(base_url="https://data-api.polymarket.com")

    with pytest.raises(PositionsPaginationError, match="0x111"):
        client.get_positions("0x111")


@respx.mock
def test_get_positions_rejects_duplicate_entries_across_moving_pages():
    first_page = [
        {
            **POSITIONS_PAGE[0],
            "conditionId": f"0x{index:064x}",
            "asset": str(index),
        }
        for index in range(500)
    ]
    second_page = [first_page[-1]]

    def respond(request):
        page = first_page if request.url.params["offset"] == "0" else second_page
        return httpx.Response(200, json=page)

    respx.get("https://data-api.polymarket.com/positions").mock(side_effect=respond)
    client = DataApiClient(base_url="https://data-api.polymarket.com")

    with pytest.raises(PositionsPaginationError, match="changed during pagination"):
        client.get_positions("0x111")
