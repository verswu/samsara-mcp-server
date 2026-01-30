"""
Shared pytest fixtures for samsara-mcp-server tests.

Provides mock SamsaraClient and sample API response data—no real HTTP calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any

from samsara_client import SamsaraClient


# ---------------------------------------------------------------------------
# Sample API response data (matches Samsara API shapes)
# ---------------------------------------------------------------------------

SAMPLE_VEHICLES_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "281474976712793",
            "name": "Truck 1",
            "serial": "1HGBH41JXMN109186",
            "tags": [{"id": "1234", "name": "West Coast"}],
        }
    ],
    "pagination": {"endCursor": "cursor-abc", "hasNextPage": False},
}

SAMPLE_GET_VEHICLE_RESPONSE: dict[str, Any] = {
    "data": {
        "id": "281474976712793",
        "name": "Truck 1",
        "serial": "1HGBH41JXMN109186",
        "tags": [{"id": "1234", "name": "West Coast"}],
    }
}

SAMPLE_UPDATE_VEHICLE_RESPONSE: dict[str, Any] = {
    "data": {
        "id": "281474976712793",
        "name": "Truck 1 Updated",
        "serial": "1HGBH41JXMN109186",
    }
}

SAMPLE_LOCATIONS_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "281474976712793",
            "location": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "time": "2025-01-15T12:00:00Z",
            },
            "speed": {"value": 45.0, "unit": "MilesPerHour"},
        }
    ],
    "pagination": {"endCursor": "cursor-xyz", "hasNextPage": False},
}

SAMPLE_SAFETY_EVENTS_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "evt-1",
            "behaviorLabel": "HarshBraking",
            "asset": {"id": "281474976712793", "name": "Truck 1"},
            "driver": {"id": "driver-1", "name": "Jane Doe"},
        }
    ],
    "pagination": {"endCursor": "cursor-evt", "hasNextPage": False},
}

SAMPLE_SAFETY_EVENTS_BY_ID_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "evt-uuid-1",
            "behaviorLabel": "HarshBraking",
            "asset": {"id": "281474976712793", "name": "Truck 1"},
            "driver": {"id": "driver-1", "name": "Jane Doe"},
        }
    ],
    "pagination": {"endCursor": "cursor-evt-id", "hasNextPage": False},
}

SAMPLE_TRIPS_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "trip-1",
            "assetId": "281474976712793",
            "startTime": "2025-01-15T08:00:00Z",
            "endTime": "2025-01-15T10:30:00Z",
            "distance": {"value": 120.5, "unit": "Miles"},
        }
    ],
    "pagination": {"endCursor": "cursor-trip", "hasNextPage": False},
}

SAMPLE_DRIVERS_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "driver-1",
            "name": "Jane Doe",
            "username": "janedoe",
            "licenseNumber": "E1234567",
            "licenseState": "CA",
        }
    ],
    "pagination": {"endCursor": "cursor-drv", "hasNextPage": False},
}

SAMPLE_CREATE_DRIVER_RESPONSE: dict[str, Any] = {
    "data": {
        "id": "driver-new-1",
        "name": "New Driver",
        "username": "newdriver",
    }
}

SAMPLE_GET_DRIVER_RESPONSE: dict[str, Any] = {
    "data": {
        "id": "driver-123",
        "name": "Jane Doe",
        "username": "janedoe",
        "licenseNumber": "E1234567",
        "licenseState": "CA",
    }
}

SAMPLE_UPDATE_DRIVER_RESPONSE: dict[str, Any] = {
    "data": {
        "id": "driver-123",
        "name": "Jane Doe Updated",
        "username": "janedoe",
        "driverActivationStatus": "active",
    }
}

SAMPLE_ORG_INFO_RESPONSE: dict[str, Any] = {
    "data": {
        "id": "org-123",
        "name": "Acme Fleet",
        "settings": {"locale": "us"},
    }
}

SAMPLE_GATEWAYS_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "gw-1",
            "name": "Gateway 1",
            "model": "AG24",
            "serial": "GW-SERIAL-001",
            "tags": [{"id": "tag-1", "name": "Warehouse"}],
        }
    ],
    "pagination": {"endCursor": "cursor-gw", "hasNextPage": False},
}


# ---------------------------------------------------------------------------
# Mock SamsaraClient (no real HTTP)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient used by SamsaraClient. No real HTTP calls."""
    client = AsyncMock()
    # Default: successful JSON response
    client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value=SAMPLE_VEHICLES_RESPONSE),
        headers={},
        text="",
    ))
    client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value=SAMPLE_CREATE_DRIVER_RESPONSE),
        headers={},
        text="",
    ))
    return client


@pytest.fixture
def mock_samsara_client(mock_httpx_client):
    """
    A SamsaraClient whose HTTP client is replaced with a mock.
    Use patch to inject mock_httpx_client before SamsaraClient() is created.
    """
    # Caller should patch httpx.AsyncClient to return mock_httpx_client,
    # then instantiate SamsaraClient(api_token="test-token").
    return mock_httpx_client


@pytest.fixture
def sample_vehicles_response():
    """Sample GET /fleet/vehicles response."""
    return SAMPLE_VEHICLES_RESPONSE


@pytest.fixture
def sample_get_vehicle_response():
    """Sample GET /fleet/vehicles/{id} (single vehicle) response."""
    return SAMPLE_GET_VEHICLE_RESPONSE


@pytest.fixture
def sample_update_vehicle_response():
    """Sample PATCH /fleet/vehicles/{id} (updated vehicle) response."""
    return SAMPLE_UPDATE_VEHICLE_RESPONSE


@pytest.fixture
def sample_locations_response():
    """Sample GET /assets/location-and-speed/stream response."""
    return SAMPLE_LOCATIONS_RESPONSE


@pytest.fixture
def sample_safety_events_response():
    """Sample GET /safety-events/stream response."""
    return SAMPLE_SAFETY_EVENTS_RESPONSE


@pytest.fixture
def sample_safety_events_by_id_response():
    """Sample GET /safety-events (by ID) response."""
    return SAMPLE_SAFETY_EVENTS_BY_ID_RESPONSE


@pytest.fixture
def sample_trips_response():
    """Sample GET /trips/stream response."""
    return SAMPLE_TRIPS_RESPONSE


@pytest.fixture
def sample_drivers_response():
    """Sample GET /fleet/drivers response."""
    return SAMPLE_DRIVERS_RESPONSE


@pytest.fixture
def sample_create_driver_response():
    """Sample POST /fleet/drivers response."""
    return SAMPLE_CREATE_DRIVER_RESPONSE


@pytest.fixture
def sample_get_driver_response():
    """Sample GET /fleet/drivers/{id} (single driver) response."""
    return SAMPLE_GET_DRIVER_RESPONSE


@pytest.fixture
def sample_update_driver_response():
    """Sample PATCH /fleet/drivers/{id} (updated driver) response."""
    return SAMPLE_UPDATE_DRIVER_RESPONSE


@pytest.fixture
def sample_org_info_response():
    """Sample GET /me (organization info) response."""
    return SAMPLE_ORG_INFO_RESPONSE


@pytest.fixture
def sample_gateways_response():
    """Sample GET /gateways response."""
    return SAMPLE_GATEWAYS_RESPONSE
