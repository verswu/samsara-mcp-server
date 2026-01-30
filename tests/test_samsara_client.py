"""
Unit tests for SamsaraClient (samsara_client.py).

All HTTP calls are mocked via unittest.mock.patch on httpx.AsyncClient.
No real API requests are made.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from samsara_client import (
    SamsaraClient,
    SamsaraError,
    SamsaraAPIError,
    SamsaraRateLimitError,
)
from tests.conftest import (
    SAMPLE_VEHICLES_RESPONSE,
    SAMPLE_LOCATIONS_RESPONSE,
    SAMPLE_SAFETY_EVENTS_RESPONSE,
    SAMPLE_SAFETY_EVENTS_BY_ID_RESPONSE,
    SAMPLE_TRIPS_RESPONSE,
    SAMPLE_DRIVERS_RESPONSE,
    SAMPLE_CREATE_DRIVER_RESPONSE,
    SAMPLE_GET_DRIVER_RESPONSE,
    SAMPLE_UPDATE_DRIVER_RESPONSE,
    SAMPLE_GET_VEHICLE_RESPONSE,
    SAMPLE_UPDATE_VEHICLE_RESPONSE,
    SAMPLE_ORG_INFO_RESPONSE,
    SAMPLE_GATEWAYS_RESPONSE,
)


def _make_response(status_code: int, json_data: dict | None = None, headers: dict | None = None):
    """Build a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.text = ""
    resp.json = MagicMock(return_value=json_data or {})
    return resp


@pytest.fixture
def mock_httpx_client():
    """Mock AsyncClient; capture get/post calls and return configurable responses."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=_make_response(200, SAMPLE_VEHICLES_RESPONSE))
    client.post = AsyncMock(return_value=_make_response(200, SAMPLE_CREATE_DRIVER_RESPONSE))
    return client


@pytest.fixture
def client(mock_httpx_client):
    """SamsaraClient with mocked httpx.AsyncClient (no real HTTP)."""
    with patch("samsara_client.httpx.AsyncClient", return_value=mock_httpx_client):
        with patch.dict("os.environ", {"SAMSARA_API_TOKEN": "test-token"}, clear=False):
            yield SamsaraClient(api_token="test-token")


# ---------------------------------------------------------------------------
# list_vehicles — query params and defaults
# ---------------------------------------------------------------------------

async def test_list_vehicles_builds_correct_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_VEHICLES_RESPONSE)
    await client.list_vehicles(
        limit=10,
        after="cursor-1",
        parent_tag_ids="1,2",
        tag_ids="3,4",
        attribute_value_ids="uuid-a",
        attributes=["attr:value"],
        updated_after_time="2025-01-01T00:00:00Z",
        created_after_time="2025-01-02T00:00:00Z",
    )
    mock_httpx_client.get.assert_called_once_with(
        "/fleet/vehicles",
        params={
            "limit": 10,
            "after": "cursor-1",
            "parentTagIds": "1,2",
            "tagIds": "3,4",
            "attributeValueIds": "uuid-a",
            "attributes": ["attr:value"],
            "updatedAfterTime": "2025-01-01T00:00:00Z",
            "createdAfterTime": "2025-01-02T00:00:00Z",
        },
    )


async def test_list_vehicles_default_values_empty_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_VEHICLES_RESPONSE)
    result = await client.list_vehicles()
    assert result == SAMPLE_VEHICLES_RESPONSE
    mock_httpx_client.get.assert_called_once_with("/fleet/vehicles", params={})


# ---------------------------------------------------------------------------
# get_vehicle — path param
# ---------------------------------------------------------------------------

async def test_get_vehicle_builds_correct_request(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_GET_VEHICLE_RESPONSE)
    await client.get_vehicle(id="281474976712793")
    mock_httpx_client.get.assert_called_once_with(
        "/fleet/vehicles/281474976712793",
        params={},
    )


async def test_get_vehicle_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.get_vehicle(id="281474976712793")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# update_vehicle — PATCH path + body
# ---------------------------------------------------------------------------

async def test_update_vehicle_sends_correct_request(client, mock_httpx_client):
    mock_httpx_client.patch.return_value = _make_response(200, SAMPLE_UPDATE_VEHICLE_RESPONSE)
    body = {"name": "Truck 1 Updated"}
    result = await client.update_vehicle(id="281474976712793", vehicle=body)
    assert result == SAMPLE_UPDATE_VEHICLE_RESPONSE
    mock_httpx_client.patch.assert_called_once_with(
        "/fleet/vehicles/281474976712793",
        json=body,
    )


async def test_update_vehicle_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.patch.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.update_vehicle(id="281474976712793", vehicle={})
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_asset_locations — query params and defaults
# ---------------------------------------------------------------------------

async def test_get_asset_locations_builds_correct_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_LOCATIONS_RESPONSE)
    await client.get_asset_locations(
        after="c1",
        limit=100,
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-01T23:59:59Z",
        ids="id1,id2",
        include_speed=True,
        include_reverse_geo=True,
    )
    mock_httpx_client.get.assert_called_once_with(
        "/assets/location-and-speed/stream",
        params={
            "after": "c1",
            "limit": 100,
            "startTime": "2025-01-01T00:00:00Z",
            "endTime": "2025-01-01T23:59:59Z",
            "ids": "id1,id2",
            "includeSpeed": True,
            "includeReverseGeo": True,
        },
    )


async def test_get_asset_locations_default_values(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_LOCATIONS_RESPONSE)
    result = await client.get_asset_locations(start_time="2025-01-01T00:00:00Z")
    assert result == SAMPLE_LOCATIONS_RESPONSE
    call_params = mock_httpx_client.get.call_args[1]["params"]
    assert call_params["startTime"] == "2025-01-01T00:00:00Z"
    assert "endTime" not in call_params
    assert "limit" not in call_params


# ---------------------------------------------------------------------------
# get_safety_events — query params and defaults
# ---------------------------------------------------------------------------

async def test_get_safety_events_builds_correct_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_SAFETY_EVENTS_RESPONSE)
    await client.get_safety_events(
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-07T00:00:00Z",
        query_by_time_field="createdAtTime",
        asset_ids="a1",
        driver_ids="d1",
        tag_ids="t1",
        behavior_labels="HarshBraking",
        event_states="needsReview",
        include_asset=True,
        include_driver=True,
        after="cursor",
    )
    mock_httpx_client.get.assert_called_once_with(
        "/safety-events/stream",
        params={
            "startTime": "2025-01-01T00:00:00Z",
            "endTime": "2025-01-07T00:00:00Z",
            "queryByTimeField": "createdAtTime",
            "assetIds": "a1",
            "driverIds": "d1",
            "tagIds": "t1",
            "behaviorLabels": "HarshBraking",
            "eventStates": "needsReview",
            "includeAsset": True,
            "includeDriver": True,
            "after": "cursor",
        },
    )


async def test_get_safety_events_required_start_time_in_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_SAFETY_EVENTS_RESPONSE)
    await client.get_safety_events(start_time="2025-01-01T00:00:00Z")
    call_params = mock_httpx_client.get.call_args[1]["params"]
    assert call_params["startTime"] == "2025-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# get_safety_events_by_id — required safetyEventIds, optional params
# ---------------------------------------------------------------------------

async def test_get_safety_events_by_id_builds_correct_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_SAFETY_EVENTS_BY_ID_RESPONSE)
    await client.get_safety_events_by_id(
        safety_event_ids=["evt-uuid-1", "evt-uuid-2"],
        include_asset=True,
        include_driver=True,
        after="cursor-1",
    )
    mock_httpx_client.get.assert_called_once_with(
        "/safety-events",
        params={
            "safetyEventIds": ["evt-uuid-1", "evt-uuid-2"],
            "includeAsset": True,
            "includeDriver": True,
            "after": "cursor-1",
        },
    )


async def test_get_safety_events_by_id_only_required(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_SAFETY_EVENTS_BY_ID_RESPONSE)
    result = await client.get_safety_events_by_id(safety_event_ids=["evt-1"])
    assert result == SAMPLE_SAFETY_EVENTS_BY_ID_RESPONSE
    mock_httpx_client.get.assert_called_once_with(
        "/safety-events",
        params={"safetyEventIds": ["evt-1"]},
    )


async def test_get_safety_events_by_id_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.get_safety_events_by_id(safety_event_ids=["evt-1"])
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_trips — query params and defaults
# ---------------------------------------------------------------------------

async def test_get_trips_builds_correct_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_TRIPS_RESPONSE)
    await client.get_trips(
        ids="id1,id2",
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-07T00:00:00Z",
        query_by="tripStartTime",
        completion_status="completed",
        include_asset=True,
        after="c1",
    )
    mock_httpx_client.get.assert_called_once_with(
        "/trips/stream",
        params={
            "ids": "id1,id2",
            "startTime": "2025-01-01T00:00:00Z",
            "endTime": "2025-01-07T00:00:00Z",
            "queryBy": "tripStartTime",
            "completionStatus": "completed",
            "includeAsset": True,
            "after": "c1",
        },
    )


async def test_get_trips_required_ids_and_start_time(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_TRIPS_RESPONSE)
    await client.get_trips(ids="v1", start_time="2025-01-01T00:00:00Z")
    call_params = mock_httpx_client.get.call_args[1]["params"]
    assert call_params["ids"] == "v1"
    assert call_params["startTime"] == "2025-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# list_drivers — query params and defaults
# ---------------------------------------------------------------------------

async def test_list_drivers_builds_correct_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_DRIVERS_RESPONSE)
    await client.list_drivers(
        driver_activation_status="deactivated",
        limit=50,
        after="c1",
        tag_ids="t1,t2",
        updated_after_time="2025-01-01T00:00:00Z",
    )
    mock_httpx_client.get.assert_called_once_with(
        "/fleet/drivers",
        params={
            "driverActivationStatus": "deactivated",
            "limit": 50,
            "after": "c1",
            "tagIds": "t1,t2",
            "updatedAfterTime": "2025-01-01T00:00:00Z",
        },
    )


async def test_list_drivers_default_empty_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_DRIVERS_RESPONSE)
    result = await client.list_drivers()
    assert result == SAMPLE_DRIVERS_RESPONSE
    mock_httpx_client.get.assert_called_once_with("/fleet/drivers", params={})


# ---------------------------------------------------------------------------
# list_gateways — query params and defaults
# ---------------------------------------------------------------------------

async def test_list_gateways_builds_correct_params(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_GATEWAYS_RESPONSE)
    await client.list_gateways(models=["AG24", "AG32"], after="cursor-gw")
    mock_httpx_client.get.assert_called_once_with(
        "/gateways",
        params={"models": ["AG24", "AG32"], "after": "cursor-gw"},
    )


async def test_list_gateways_default_values(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_GATEWAYS_RESPONSE)
    result = await client.list_gateways()
    assert result == SAMPLE_GATEWAYS_RESPONSE
    mock_httpx_client.get.assert_called_once_with("/gateways", params={})


async def test_list_gateways_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.list_gateways()
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# create_driver — POST body
# ---------------------------------------------------------------------------

async def test_create_driver_sends_correct_body(client, mock_httpx_client):
    mock_httpx_client.post.return_value = _make_response(200, SAMPLE_CREATE_DRIVER_RESPONSE)
    body = {"name": "Jane Doe", "username": "janedoe", "password": "secret123"}
    result = await client.create_driver(body)
    assert result == SAMPLE_CREATE_DRIVER_RESPONSE
    mock_httpx_client.post.assert_called_once_with("/fleet/drivers", json=body)


# ---------------------------------------------------------------------------
# get_driver — path param
# ---------------------------------------------------------------------------

async def test_get_driver_builds_correct_request(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_GET_DRIVER_RESPONSE)
    await client.get_driver(id="driver-123")
    mock_httpx_client.get.assert_called_once_with(
        "/fleet/drivers/driver-123",
        params={},
    )


async def test_get_driver_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.get_driver(id="driver-123")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# update_driver — PATCH path + body
# ---------------------------------------------------------------------------

async def test_update_driver_sends_correct_request(client, mock_httpx_client):
    mock_httpx_client.patch.return_value = _make_response(200, SAMPLE_UPDATE_DRIVER_RESPONSE)
    body = {"name": "Jane Doe Updated", "driverActivationStatus": "active"}
    result = await client.update_driver(id="driver-123", driver=body)
    assert result == SAMPLE_UPDATE_DRIVER_RESPONSE
    mock_httpx_client.patch.assert_called_once_with(
        "/fleet/drivers/driver-123",
        json=body,
    )


async def test_update_driver_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.patch.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.update_driver(id="driver-123", driver={})
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_organization_info — GET /me, no params
# ---------------------------------------------------------------------------

async def test_get_organization_info_calls_me_endpoint(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, SAMPLE_ORG_INFO_RESPONSE)
    result = await client.get_organization_info()
    assert result == SAMPLE_ORG_INFO_RESPONSE
    mock_httpx_client.get.assert_called_once_with("/me")


async def test_get_organization_info_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.get_organization_info()
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Error handling: 401, 429, 500
# ---------------------------------------------------------------------------

async def test_list_vehicles_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(
        401,
        {"message": "Invalid or expired token"},
    )
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.list_vehicles()
    assert exc_info.value.status_code == 401
    msg = str(exc_info.value)
    assert "token" in msg.lower() or "401" in msg


async def test_list_vehicles_429_raises_rate_limit_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(
        429,
        {"message": "Rate limit exceeded"},
        headers={"Retry-After": "60"},
    )
    with pytest.raises(SamsaraRateLimitError) as exc_info:
        await client.list_vehicles()
    assert exc_info.value.retry_after == 60


async def test_list_vehicles_500_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(
        500,
        {"message": "Internal server error"},
    )
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.list_vehicles()
    assert exc_info.value.status_code == 500


async def test_create_driver_429_raises_rate_limit_error(client, mock_httpx_client):
    mock_httpx_client.post.return_value = _make_response(
        429,
        {"message": "Too many requests"},
        headers={"Retry-After": "30"},
    )
    with pytest.raises(SamsaraRateLimitError) as exc_info:
        await client.create_driver({"name": "A", "username": "a", "password": "p"})
    assert exc_info.value.retry_after == 30


async def test_get_asset_locations_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {"message": "Unauthorized"})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.get_asset_locations(start_time="2025-01-01T00:00:00Z")
    assert exc_info.value.status_code == 401
