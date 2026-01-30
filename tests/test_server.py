"""
MCP tool registration tests for server.py.

Verifies all tools are registered, have inputSchema properties, and descriptions.
Does not make real API calls; call_tool is not exercised against live API.
"""

import pytest

# Import list_tools from server (the registered handler returns the tool list)
from server import list_tools


# Expected tools
EXPECTED_TOOL_NAMES = [
    "list_vehicles",
    "get_vehicle",
    "update_vehicle",
    "get_asset_locations",
    "get_safety_events",
    "get_safety_events_by_id",
    "get_trips",
    "get_drivers",
    "create_driver",
    "get_driver",
    "update_driver",
    "list_gateways",
    "get_org_info",
]

# Tools that have required fields in inputSchema
TOOLS_WITH_REQUIRED = {
    "get_trips": ["ids"],
    "get_safety_events_by_id": ["safetyEventIds"],
    "create_driver": ["name", "username", "password"],
    "get_driver": ["id"],
    "update_driver": ["id", "body"],
    "get_vehicle": ["id"],
    "update_vehicle": ["id", "body"],
}


@pytest.fixture
async def tools():
    """Fetch the list of tools from the MCP server (no HTTP, just the registered list)."""
    return await list_tools()


# ---------------------------------------------------------------------------
# All tools registered
# ---------------------------------------------------------------------------

async def test_all_tools_are_registered(tools):
    """All expected tools appear in list_tools()."""
    names = [t.name for t in tools]
    for expected in EXPECTED_TOOL_NAMES:
        assert expected in names, f"Tool {expected!r} not registered. Got: {names}"


async def test_tool_count(tools):
    """Exactly the expected number of tools."""
    assert len(tools) == len(EXPECTED_TOOL_NAMES)


# ---------------------------------------------------------------------------
# inputSchema: type object and properties
# ---------------------------------------------------------------------------

async def test_each_tool_has_input_schema(tools):
    """Every tool has an inputSchema with type and properties."""
    for tool in tools:
        assert hasattr(tool, "inputSchema"), f"{tool.name} missing inputSchema"
        schema = tool.inputSchema
        assert isinstance(schema, dict), f"{tool.name} inputSchema not a dict"
        assert schema.get("type") == "object", f"{tool.name} inputSchema.type should be 'object'"
        assert "properties" in schema, f"{tool.name} inputSchema missing 'properties'"
        assert isinstance(schema["properties"], dict), f"{tool.name} inputSchema.properties not a dict"


async def test_tools_with_required_have_required_key(tools):
    """Tools that require parameters have inputSchema.required and correct keys."""
    by_name = {t.name: t for t in tools}
    for tool_name, required_list in TOOLS_WITH_REQUIRED.items():
        assert tool_name in by_name, f"Tool {tool_name} not in tools"
        schema = by_name[tool_name].inputSchema
        assert "required" in schema, f"{tool_name} should have inputSchema.required"
        assert schema["required"] == required_list, (
            f"{tool_name} required should be {required_list}, got {schema.get('required')}"
        )


async def test_list_vehicles_schema_properties(tools):
    """list_vehicles has expected inputSchema properties."""
    tool = next(t for t in tools if t.name == "list_vehicles")
    props = tool.inputSchema["properties"]
    expected = {"limit", "after", "parentTagIds", "tagIds", "attributeValueIds", "attributes", "updatedAfterTime", "createdAfterTime"}
    assert expected.issubset(props.keys()), f"list_vehicles missing properties: {expected - props.keys()}"


async def test_get_vehicle_schema_properties_and_required(tools):
    """get_vehicle has inputSchema with id property and required id."""
    tool = next(t for t in tools if t.name == "get_vehicle")
    props = tool.inputSchema["properties"]
    assert "id" in props, "get_vehicle missing 'id' property"
    assert tool.inputSchema.get("required") == ["id"]


async def test_update_vehicle_schema_properties_and_required(tools):
    """update_vehicle has inputSchema with id, body and required id, body."""
    tool = next(t for t in tools if t.name == "update_vehicle")
    props = tool.inputSchema["properties"]
    assert "id" in props and "body" in props, "update_vehicle missing 'id' or 'body' property"
    assert set(tool.inputSchema.get("required", [])) == {"id", "body"}


async def test_get_asset_locations_schema_properties(tools):
    """get_asset_locations has expected inputSchema properties."""
    tool = next(t for t in tools if t.name == "get_asset_locations")
    props = tool.inputSchema["properties"]
    expected = {"after", "limit", "startTime", "endTime", "ids", "includeSpeed", "includeReverseGeo"}
    assert expected.issubset(props.keys()), f"get_asset_locations missing properties: {expected - props.keys()}"


async def test_get_safety_events_schema_properties(tools):
    """get_safety_events has expected inputSchema properties."""
    tool = next(t for t in tools if t.name == "get_safety_events")
    props = tool.inputSchema["properties"]
    expected = {"startTime", "endTime", "queryByTimeField", "assetIds", "driverIds", "tagIds", "behaviorLabels", "eventStates", "includeAsset", "includeDriver", "after"}
    assert expected.issubset(props.keys()), f"get_safety_events missing properties: {expected - props.keys()}"


async def test_get_safety_events_by_id_schema_properties(tools):
    """get_safety_events_by_id has expected inputSchema properties and required safetyEventIds."""
    tool = next(t for t in tools if t.name == "get_safety_events_by_id")
    props = tool.inputSchema["properties"]
    expected = {"safetyEventIds", "includeAsset", "includeDriver", "includeVgOnlyEvents", "after"}
    assert expected.issubset(props.keys()), f"get_safety_events_by_id missing properties: {expected - props.keys()}"
    assert tool.inputSchema["required"] == ["safetyEventIds"]


async def test_get_trips_schema_properties(tools):
    """get_trips has expected inputSchema properties and required ids."""
    tool = next(t for t in tools if t.name == "get_trips")
    props = tool.inputSchema["properties"]
    expected = {"ids", "startTime", "endTime", "queryBy", "completionStatus", "includeAsset", "after"}
    assert expected.issubset(props.keys()), f"get_trips missing properties: {expected - props.keys()}"
    assert tool.inputSchema["required"] == ["ids"]


async def test_get_drivers_schema_properties(tools):
    """get_drivers has expected inputSchema properties."""
    tool = next(t for t in tools if t.name == "get_drivers")
    props = tool.inputSchema["properties"]
    expected = {"driverActivationStatus", "limit", "after", "tagIds", "updatedAfterTime", "createdAfterTime"}
    assert expected.issubset(props.keys()), f"get_drivers missing properties: {expected - props.keys()}"


async def test_list_gateways_schema_properties(tools):
    """list_gateways has expected inputSchema properties."""
    tool = next(t for t in tools if t.name == "list_gateways")
    props = tool.inputSchema["properties"]
    expected = {"models", "after"}
    assert expected.issubset(props.keys()), f"list_gateways missing properties: {expected - props.keys()}"


async def test_create_driver_schema_properties_and_required(tools):
    """create_driver has expected inputSchema properties and required name, username, password."""
    tool = next(t for t in tools if t.name == "create_driver")
    props = tool.inputSchema["properties"]
    expected = {"name", "username", "password", "licenseNumber", "licenseState", "phone", "notes", "tagIds", "timezone"}
    assert expected.issubset(props.keys()), f"create_driver missing properties: {expected - props.keys()}"
    assert set(tool.inputSchema["required"]) == {"name", "username", "password"}


async def test_get_driver_schema_properties_and_required(tools):
    """get_driver has inputSchema with id property and required id."""
    tool = next(t for t in tools if t.name == "get_driver")
    props = tool.inputSchema["properties"]
    assert "id" in props, "get_driver missing 'id' property"
    assert tool.inputSchema.get("required") == ["id"]


async def test_update_driver_schema_properties_and_required(tools):
    """update_driver has inputSchema with id, body and required id, body."""
    tool = next(t for t in tools if t.name == "update_driver")
    props = tool.inputSchema["properties"]
    assert "id" in props and "body" in props, "update_driver missing 'id' or 'body' property"
    assert set(tool.inputSchema.get("required", [])) == {"id", "body"}


async def test_get_org_info_schema_properties(tools):
    """get_org_info has inputSchema with type object; no required params."""
    tool = next(t for t in tools if t.name == "get_org_info")
    assert tool.inputSchema.get("type") == "object"
    assert "properties" in tool.inputSchema
    assert tool.inputSchema["properties"] == {}
    assert "required" not in tool.inputSchema or tool.inputSchema.get("required") == []


# ---------------------------------------------------------------------------
# Descriptions present
# ---------------------------------------------------------------------------

async def test_each_tool_has_description(tools):
    """Every tool has a non-empty description."""
    for tool in tools:
        assert hasattr(tool, "description"), f"{tool.name} missing description"
        assert tool.description and tool.description.strip(), (
            f"{tool.name} has empty description"
        )


async def test_descriptions_are_informative(tools):
    """Tool descriptions mention relevant concepts (vehicles, drivers, etc.)."""
    by_name = {t.name: t for t in tools}
    assert "vehicle" in by_name["list_vehicles"].description.lower()
    assert "vehicle" in by_name["get_vehicle"].description.lower() or "retrieve" in by_name["get_vehicle"].description.lower()
    assert "update" in by_name["update_vehicle"].description.lower() or "vehicle" in by_name["update_vehicle"].description.lower()
    assert "location" in by_name["get_asset_locations"].description.lower() or "gps" in by_name["get_asset_locations"].description.lower()
    assert "safety" in by_name["get_safety_events"].description.lower() or "event" in by_name["get_safety_events"].description.lower()
    assert "safety" in by_name["get_safety_events_by_id"].description.lower() or "event" in by_name["get_safety_events_by_id"].description.lower() or "id" in by_name["get_safety_events_by_id"].description.lower()
    assert "trip" in by_name["get_trips"].description.lower()
    assert "driver" in by_name["get_drivers"].description.lower()
    assert "create" in by_name["create_driver"].description.lower() or "driver" in by_name["create_driver"].description.lower()
    assert "driver" in by_name["get_driver"].description.lower() or "retrieve" in by_name["get_driver"].description.lower()
    assert "update" in by_name["update_driver"].description.lower() or "driver" in by_name["update_driver"].description.lower()
    assert "gateway" in by_name["list_gateways"].description.lower() or "list" in by_name["list_gateways"].description.lower()
    assert "organization" in by_name["get_org_info"].description.lower() or "org" in by_name["get_org_info"].description.lower()
