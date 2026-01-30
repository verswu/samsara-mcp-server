"""
MCP Server for Samsara API integration.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Sequence

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from samsara_client import SamsaraClient, SamsaraError, SamsaraRateLimitError, SamsaraAPIError

# Load environment variables from .env file
load_dotenv()


# Create a single Samsara client instance at module level
# This will be initialized once at startup
_samsara_client: SamsaraClient | None = None


def get_samsara_client() -> SamsaraClient:
    """Get or create the Samsara client instance."""
    global _samsara_client
    if _samsara_client is None:
        api_token = os.getenv("SAMSARA_API_TOKEN")
        if not api_token:
            raise ValueError(
                "SAMSARA_API_TOKEN environment variable is required"
            )
        _samsara_client = SamsaraClient(api_token=api_token)
    return _samsara_client


# Create MCP server instance
server = Server("samsara-mcp-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_vehicles",
            description=(
                "List all vehicles from the Samsara fleet. "
                "Supports filtering by tags, attributes, and time ranges. "
                "Rate limit: 25 requests/sec."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": (
                            "The limit for how many objects will be in the response. "
                            "Default and max for this value is 512 objects."
                        ),
                        "minimum": 1,
                        "maximum": 512,
                    },
                    "after": {
                        "type": "string",
                        "description": (
                            "If specified, this should be the endCursor value from "
                            "the previous page of results. When present, this request "
                            "will return the next page of results that occur immediately "
                            "after the previous page of results."
                        ),
                    },
                    "parentTagIds": {
                        "type": "string",
                        "description": (
                            "A filter on the data based on this comma-separated list of "
                            "parent tag IDs, for use by orgs with tag hierarchies. "
                            "Specifying a parent tag will implicitly include all descendent "
                            "tags of the parent tag. Example: '345,678'"
                        ),
                    },
                    "tagIds": {
                        "type": "string",
                        "description": (
                            "A filter on the data based on this comma-separated list of "
                            "tag IDs. Example: '1234,5678'"
                        ),
                    },
                    "attributeValueIds": {
                        "type": "string",
                        "description": (
                            "A filter on the data based on this comma-separated list of "
                            "attribute value IDs. Only entities associated with ALL of the "
                            "referenced values will be returned. Example: "
                            "'076efac2-83b5-47aa-ba36-18428436dcac,6707b3f0-23b9-4fe3-b7be-11be34aea544'"
                        ),
                    },
                    "attributes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "A filter on the data to return entities having given attributes "
                            "using either name-value pair, or range query (only for numeric "
                            "and date attributes) separated by a comma. Only entities meeting "
                            "all the conditions will be returned. Example: "
                            "['ExampleAttributeName:some_value', 'SomeOtherAttr:123', "
                            "'Length:range(10,20)', 'Date:range(2025-01-01,2025-01-31)']"
                        ),
                    },
                    "updatedAfterTime": {
                        "type": "string",
                        "description": (
                            "A filter on data to have an updated at time after or equal to "
                            "this specified time in RFC 3339 format. Millisecond precision "
                            "and timezones are supported. Examples: 2019-06-13T19:08:25Z, "
                            "2019-06-13T19:08:25.455Z, OR 2015-09-15T14:00:12-04:00"
                        ),
                    },
                    "createdAfterTime": {
                        "type": "string",
                        "description": (
                            "A filter on data to have a created at time after or equal to "
                            "this specified time in RFC 3339 format. Millisecond precision "
                            "and timezones are supported. Examples: 2019-06-13T19:08:25Z, "
                            "2019-06-13T19:08:25.455Z, OR 2015-09-15T14:00:12-04:00"
                        ),
                    },
                },
            },
        ),
        Tool(
            name="get_vehicle",
            description=(
                "Retrieve a single vehicle by ID. Use Samsara vehicle ID or external ID "
                "(e.g. maintenanceId:250020 or samsara.vin:1HGBH41JXMN109186). Requires Read Vehicles scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": (
                            "ID of the vehicle. Samsara ID or external ID in key:value format "
                            "(e.g. maintenanceId:250020, samsara.vin:1HGBH41JXMN109186)."
                        ),
                    },
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="update_vehicle",
            description=(
                "Update a vehicle by ID. Pass only the fields to update (e.g. name, notes, tagIds). "
                "No required fields in body. Requires Write Vehicles scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": (
                            "ID of the vehicle. Samsara ID or external ID in key:value format."
                        ),
                    },
                    "body": {
                        "type": "object",
                        "description": "Fields to update (UpdateVehicleRequest). Only include fields you wish to patch.",
                    },
                },
                "required": ["id", "body"],
            },
        ),
        Tool(
            name="get_asset_locations",
            description=(
                "Get current location and speed data for assets. "
                "Returns GPS coordinates, optional street addresses, and speed. "
                "Use includeReverseGeo=true to get human-readable addresses. "
                "By default, returns recent data (last 5 minutes) with addresses and speed included."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "after": {
                        "type": "string",
                        "description": "Pagination cursor from previous response.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (default 512, max 512).",
                        "minimum": 1,
                        "maximum": 512,
                    },
                    "startTime": {
                        "type": "string",
                        "description": (
                            "Start time in RFC 3339 format. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                    "endTime": {
                        "type": "string",
                        "description": (
                            "End time in RFC 3339 format. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                    "ids": {
                        "type": "string",
                        "description": "Comma-separated list of asset IDs to filter by.",
                    },
                    "includeSpeed": {
                        "type": "boolean",
                        "description": "Include speed data in the response.",
                    },
                    "includeReverseGeo": {
                        "type": "boolean",
                        "description": "Include street address in the response.",
                    },
                    "includeGeofenceLookup": {
                        "type": "boolean",
                        "description": "Include geofence information in the response.",
                    },
                    "includeHighFrequencyLocations": {
                        "type": "boolean",
                        "description": "Include high frequency location data.",
                    },
                    "includeExternalIds": {
                        "type": "boolean",
                        "description": "Include external IDs in the response.",
                    },
                },
            },
        ),
        Tool(
            name="get_safety_events",
            description=(
                "Get safety events like harsh braking, speeding, collisions, drowsiness, "
                "mobile usage, and seatbelt violations. Requires a start time. "
                "Use behaviorLabels to filter by event type, eventStates to filter by coaching status. "
                "Set includeDriver=true and includeAsset=true to get full context. "
                "By default, returns events from the last 7 days with driver and asset details included."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "startTime": {
                        "type": "string",
                        "description": (
                            "RFC 3339 timestamp to begin receiving data. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                    "endTime": {
                        "type": "string",
                        "description": (
                            "RFC 3339 timestamp end range. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                    "queryByTimeField": {
                        "type": "string",
                        "enum": ["updatedAtTime", "createdAtTime"],
                        "description": "Query by 'updatedAtTime' (default) or 'createdAtTime'.",
                    },
                    "assetIds": {
                        "type": "string",
                        "description": "Comma-separated asset IDs to filter by.",
                    },
                    "driverIds": {
                        "type": "string",
                        "description": "Comma-separated driver IDs to filter by.",
                    },
                    "tagIds": {
                        "type": "string",
                        "description": "Comma-separated tag IDs to filter by.",
                    },
                    "assignedCoaches": {
                        "type": "string",
                        "description": "Comma-separated coach IDs to filter by.",
                    },
                    "behaviorLabels": {
                        "type": "string",
                        "description": (
                            "Filter by behavior type. Options: Acceleration, Braking, Crash, "
                            "Speeding, HarshTurn, FollowingDistance, LaneDeparture, Drowsy, "
                            "MobileUsage, NoSeatbelt, RanRedLight, RollingStop, etc."
                        ),
                    },
                    "eventStates": {
                        "type": "string",
                        "description": (
                            "Filter by state. Options: needsReview, reviewed, needsCoaching, "
                            "coached, dismissed, needsRecognition, recognized."
                        ),
                    },
                    "includeAsset": {
                        "type": "boolean",
                        "description": "Include asset details in response.",
                    },
                    "includeDriver": {
                        "type": "boolean",
                        "description": "Include driver details in response.",
                    },
                    "includeVgOnlyEvents": {
                        "type": "boolean",
                        "description": "Include video-only events.",
                    },
                    "after": {
                        "type": "string",
                        "description": "Pagination cursor from previous response.",
                    },
                },
            },
        ),
        Tool(
            name="get_safety_events_by_id",
            description=(
                "Get details for specified safety events by ID. Requires a list of safety event IDs (UUIDs). "
                "Use get_safety_events (stream) first to discover event IDs. "
                "Optional: includeAsset, includeDriver, includeVgOnlyEvents for expanded data; after for pagination. "
                "Rate limit: 5 requests/sec. Scope: Read Safety Events & Scores (Safety & Cameras)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "safetyEventIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Required. Comma-separated or array of safety event IDs (Samsara UUIDs). "
                            "Use get_safety_events to get event IDs first."
                        ),
                    },
                    "includeAsset": {
                        "type": "boolean",
                        "description": "Include expanded asset data in response.",
                    },
                    "includeDriver": {
                        "type": "boolean",
                        "description": "Include expanded driver data in response.",
                    },
                    "includeVgOnlyEvents": {
                        "type": "boolean",
                        "description": "Include events from devices with only a Vehicle Gateway (VG).",
                    },
                    "after": {
                        "type": "string",
                        "description": "Pagination cursor from previous response.",
                    },
                },
                "required": ["safetyEventIds"],
            },
        ),
        Tool(
            name="get_trips",
            description=(
                "Get trip history for specific vehicles. Returns trip start/end times, "
                "locations, distance, and duration. Requires asset IDs - use list_vehicles "
                "first to get IDs if needed. Use completionStatus='inProgress' to see active "
                "trips, 'completed' for finished trips. "
                "By default, returns trips from the last 7 days with asset details included."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "string",
                        "description": (
                            "Comma-separated list of asset IDs (up to 50). Required. "
                            "Use list_vehicles to find asset IDs if you only have vehicle names."
                        ),
                    },
                    "startTime": {
                        "type": "string",
                        "description": (
                            "RFC 3339 timestamp to begin receiving data. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                    "endTime": {
                        "type": "string",
                        "description": (
                            "RFC 3339 timestamp end range. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                    "queryBy": {
                        "type": "string",
                        "enum": ["updatedAtTime", "tripStartTime"],
                        "description": "Query by 'updatedAtTime' (default) or 'tripStartTime'.",
                    },
                    "completionStatus": {
                        "type": "string",
                        "enum": ["inProgress", "completed", "all"],
                        "description": (
                            "Filter by trip status: 'inProgress' for active trips, "
                            "'completed' for finished trips, 'all' for both (default)."
                        ),
                    },
                    "includeAsset": {
                        "type": "boolean",
                        "description": "Include asset details in response.",
                    },
                    "after": {
                        "type": "string",
                        "description": "Pagination cursor from previous response.",
                    },
                },
                "required": ["ids"],
            },
        ),
        Tool(
            name="get_drivers",
            description=(
                "List all drivers in the organization. "
                "Use driverActivationStatus='active' (default) or 'deactivated'. "
                "Supports filtering by tags, attributes, and time ranges. "
                "Use 'after' with endCursor from previous response for pagination. "
                "Requires Read Drivers scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "driverActivationStatus": {
                        "type": "string",
                        "enum": ["active", "deactivated"],
                        "description": (
                            "If 'deactivated', only deactivated drivers are returned. "
                            "Defaults to 'active' if not provided."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The limit for how many objects will be in the response. Default and max is 512.",
                        "minimum": 1,
                        "maximum": 512,
                    },
                    "after": {
                        "type": "string",
                        "description": (
                            "Pagination cursor (endCursor) from the previous page of results. "
                            "When present, returns the next page."
                        ),
                    },
                    "parentTagIds": {
                        "type": "string",
                        "description": "Comma-separated list of parent tag IDs. Example: '345,678'",
                    },
                    "tagIds": {
                        "type": "string",
                        "description": "Comma-separated list of tag IDs. Example: '1234,5678'",
                    },
                    "attributeValueIds": {
                        "type": "string",
                        "description": "Comma-separated list of attribute value IDs.",
                    },
                    "attributes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filter by attributes (name-value or range). "
                            "Example: ['ExampleAttribute:value', 'NumericAttr:range(10,20)']"
                        ),
                    },
                    "updatedAfterTime": {
                        "type": "string",
                        "description": (
                            "Filter by updated at time in RFC 3339 format. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                    "createdAfterTime": {
                        "type": "string",
                        "description": (
                            "Filter by created at time in RFC 3339 format. "
                            "Example: 2019-06-13T19:08:25Z"
                        ),
                    },
                },
            },
        ),
        Tool(
            name="create_driver",
            description=(
                "Create a new driver in the organization. "
                "Requires name, password, and username. Username must be unique and cannot contain spaces or '@'. "
                "Optional: licenseNumber, licenseState, phone, notes, tagIds, timezone, externalIds, etc. "
                "Requires Write Drivers scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Driver's full name (1-255 characters).",
                        "minLength": 1,
                        "maxLength": 255,
                    },
                    "username": {
                        "type": "string",
                        "description": (
                            "Driver's login username for the driver app. Must be unique, "
                            "no spaces or '@' (1-189 characters)."
                        ),
                        "minLength": 1,
                        "maxLength": 189,
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for the driver to log into the Samsara driver app.",
                    },
                    "licenseNumber": {
                        "type": "string",
                        "description": "Driver's state-issued license number. With licenseState must be unique.",
                    },
                    "licenseState": {
                        "type": "string",
                        "description": "US state, Canadian province, or US territory abbreviation (e.g. CA).",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Driver's phone number (max 255 characters).",
                        "maxLength": 255,
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notes about the driver (max 4096 characters).",
                        "maxLength": 4096,
                    },
                    "tagIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of tags the driver is associated with. Required if API access is scoped by tags.",
                    },
                    "timezone": {
                        "type": "string",
                        "description": (
                            "Home terminal timezone (IANA key, e.g. America/Los_Angeles, America/New_York) "
                            "for ELD log calculation."
                        ),
                    },
                    "externalIds": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": "External IDs for the driver (e.g. payrollId, maintenanceId).",
                    },
                    "locale": {
                        "type": "string",
                        "enum": ["us", "at", "be", "ca", "gb", "fr", "de", "ie", "it", "lu", "mx", "nl", "es", "ch", "pr"],
                        "description": "Locale override (ISO 3166-2 country code).",
                    },
                    "eldExempt": {
                        "type": "boolean",
                        "description": "Whether the driver is exempt from the Electronic Logging Mandate.",
                    },
                    "eldExemptReason": {
                        "type": "string",
                        "description": "Reason for ELD exemption if eldExempt is true.",
                    },
                    "vehicleGroupTagId": {
                        "type": "string",
                        "description": "Tag ID that determines which vehicles the driver sees when selecting vehicles.",
                    },
                    "staticAssignedVehicleId": {
                        "type": "string",
                        "description": "ID of vehicle the driver is permanently assigned to (uncommon).",
                    },
                },
                "required": ["name", "username", "password"],
            },
        ),
        Tool(
            name="get_driver",
            description=(
                "Retrieve a single driver by ID. Use Samsara driver ID or external ID (e.g. payrollId:ABFS18600). "
                "Requires Read Drivers scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": (
                            "ID of the driver. Samsara ID or external ID in key:value format "
                            "(e.g. payrollId:ABFS18600)."
                        ),
                    },
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="update_driver",
            description=(
                "Update a driver by ID. Pass fields to update (e.g. name, phone, driverActivationStatus). "
                "Use driverActivationStatus='deactivated' to deactivate; optional deactivatedAtTime. "
                "Requires Write Drivers scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": (
                            "ID of the driver. Samsara ID or external ID in key:value format "
                            "(e.g. payrollId:ABFS18600)."
                        ),
                    },
                    "body": {
                        "type": "object",
                        "description": "Fields to update (UpdateDriverRequest). e.g. name, phone, notes, driverActivationStatus, deactivatedAtTime.",
                    },
                },
                "required": ["id", "body"],
            },
        ),
        Tool(
            name="list_gateways",
            description=(
                "List all gateways. Optional filter by gateway models and pagination with 'after'. "
                "Rate limit: 5 requests/sec. Requires Read Gateways scope under Setup & Administration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "models": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by comma-separated list of gateway models.",
                    },
                    "after": {
                        "type": "string",
                        "description": (
                            "Pagination cursor (endCursor) from the previous page of results. "
                            "When present, returns the next page."
                        ),
                    },
                },
            },
        ),
        Tool(
            name="list_tags",
            description=(
                "List all tags in the organization. Tags are used to group and filter "
                "vehicles, drivers, and other assets. Supports pagination. "
                "Requires Read Tags scope under Setup & Administration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of results (1-512, default 512).",
                    },
                    "after": {
                        "type": "string",
                        "description": "Pagination cursor from previous response.",
                    },
                },
            },
        ),
        Tool(
            name="create_tag",
            description=(
                "Create a new tag in the organization. Tags can be used to group "
                "vehicles, drivers, addresses, and other entities. "
                "Requires Write Tags scope under Setup & Administration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the tag to create.",
                    },
                    "parentTagId": {
                        "type": "string",
                        "description": "Optional parent tag ID for nested tags.",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="get_speeding_intervals",
            description=(
                "Get speeding intervals for trips. Returns speeding data for completed trips "
                "based on time parameters. Can filter by severity (light, moderate, heavy, severe). "
                "Rate limit: 5 req/sec. Requires Read Speeding Intervals scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "assetIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of asset IDs (up to 50).",
                    },
                    "startTime": {
                        "type": "string",
                        "description": "RFC 3339 timestamp for start of query range.",
                    },
                    "endTime": {
                        "type": "string",
                        "description": "RFC 3339 timestamp for end of query range (optional).",
                    },
                    "queryBy": {
                        "type": "string",
                        "enum": ["updatedAtTime", "tripStartTime"],
                        "description": "Compare times against 'updatedAtTime' (default) or 'tripStartTime'.",
                    },
                    "includeAsset": {
                        "type": "boolean",
                        "description": "Include expanded asset data.",
                    },
                    "includeDriverId": {
                        "type": "boolean",
                        "description": "Include driver ID in response.",
                    },
                    "after": {
                        "type": "string",
                        "description": "Pagination cursor from previous response.",
                    },
                    "severityLevels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by severity: 'light', 'moderate', 'heavy', 'severe'.",
                    },
                },
                "required": ["assetIds", "startTime"],
            },
        ),
        Tool(
            name="get_safety_settings",
            description=(
                "Get safety settings for the organization. Includes harsh event sensitivity, "
                "in-cab alerts, and other safety configuration. Rate limit: 5 req/sec. "
                "Requires Read Safety Events & Scores scope under Safety & Cameras."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_org_info",
            description=(
                "Get information about your organization (e.g. org name, ID, settings). "
                "No parameters required. Requires Read Org Information scope under Setup & Administration."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle tool calls."""
    client = get_samsara_client()
    
    if name == "list_vehicles":
        try:
            # Extract parameters from arguments
            limit = arguments.get("limit")
            after = arguments.get("after")
            parent_tag_ids = arguments.get("parentTagIds")
            tag_ids = arguments.get("tagIds")
            attribute_value_ids = arguments.get("attributeValueIds")
            attributes = arguments.get("attributes")
            updated_after_time = arguments.get("updatedAfterTime")
            created_after_time = arguments.get("createdAfterTime")
            
            # Call the Samsara API
            result = await client.list_vehicles(
                limit=limit,
                after=after,
                parent_tag_ids=parent_tag_ids,
                tag_ids=tag_ids,
                attribute_value_ids=attribute_value_ids,
                attributes=attributes,
                updated_after_time=updated_after_time,
                created_after_time=created_after_time,
            )
            
            # Return the result as JSON text
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]
            
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]
            
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_vehicle":
        try:
            id = arguments.get("id")
            if not id:
                return [TextContent(
                    type="text",
                    text="Error: get_vehicle requires 'id'."
                )]
            result = await client.get_vehicle(id=id)
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "update_vehicle":
        try:
            id = arguments.get("id")
            body = arguments.get("body") or {}
            if not id:
                return [TextContent(
                    type="text",
                    text="Error: update_vehicle requires 'id'."
                )]
            result = await client.update_vehicle(id=id, vehicle=body)
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_asset_locations":
        try:
            # Extract parameters from arguments
            after = arguments.get("after")
            limit = arguments.get("limit")
            start_time = arguments.get("startTime")
            end_time = arguments.get("endTime")
            ids = arguments.get("ids")
            include_speed = arguments.get("includeSpeed")
            include_reverse_geo = arguments.get("includeReverseGeo")
            include_geofence_lookup = arguments.get("includeGeofenceLookup")
            include_high_frequency_locations = arguments.get("includeHighFrequencyLocations")
            include_external_ids = arguments.get("includeExternalIds")

            # Default behavior: when no time range specified, get last 5 minutes
            # with includeReverseGeo=true and includeSpeed=true
            if start_time is None and end_time is None:
                now = datetime.now(timezone.utc)
                start_time = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
                end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

            if include_reverse_geo is None:
                include_reverse_geo = True

            if include_speed is None:
                include_speed = True

            # Call the Samsara API
            result = await client.get_asset_locations(
                after=after,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
                ids=ids,
                include_speed=include_speed,
                include_reverse_geo=include_reverse_geo,
                include_geofence_lookup=include_geofence_lookup,
                include_high_frequency_locations=include_high_frequency_locations,
                include_external_ids=include_external_ids,
            )

            # Return the result as JSON text
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_safety_events":
        try:
            # Extract parameters from arguments
            start_time = arguments.get("startTime")
            end_time = arguments.get("endTime")
            query_by_time_field = arguments.get("queryByTimeField")
            asset_ids = arguments.get("assetIds")
            driver_ids = arguments.get("driverIds")
            tag_ids = arguments.get("tagIds")
            assigned_coaches = arguments.get("assignedCoaches")
            behavior_labels = arguments.get("behaviorLabels")
            event_states = arguments.get("eventStates")
            include_asset = arguments.get("includeAsset")
            include_driver = arguments.get("includeDriver")
            include_vg_only_events = arguments.get("includeVgOnlyEvents")
            after = arguments.get("after")

            # Default behavior: when no start time specified, default to 7 days ago
            # with includeDriver=true and includeAsset=true for context
            if start_time is None:
                now = datetime.now(timezone.utc)
                start_time = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

            if include_driver is None:
                include_driver = True

            if include_asset is None:
                include_asset = True

            # Call the Samsara API
            result = await client.get_safety_events(
                start_time=start_time,
                end_time=end_time,
                query_by_time_field=query_by_time_field,
                asset_ids=asset_ids,
                driver_ids=driver_ids,
                tag_ids=tag_ids,
                assigned_coaches=assigned_coaches,
                behavior_labels=behavior_labels,
                event_states=event_states,
                include_asset=include_asset,
                include_driver=include_driver,
                include_vg_only_events=include_vg_only_events,
                after=after,
            )

            # Return the result as JSON text
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_safety_events_by_id":
        try:
            safety_event_ids_arg = arguments.get("safetyEventIds")
            if not safety_event_ids_arg:
                return [TextContent(
                    type="text",
                    text="Error: 'safetyEventIds' is required. Provide a list of safety event IDs (UUIDs). Use get_safety_events to discover event IDs."
                )]
            if isinstance(safety_event_ids_arg, list):
                safety_event_ids = [str(x) for x in safety_event_ids_arg]
            else:
                safety_event_ids = [s.strip() for s in str(safety_event_ids_arg).split(",") if s.strip()]
            include_asset = arguments.get("includeAsset")
            include_driver = arguments.get("includeDriver")
            include_vg_only_events = arguments.get("includeVgOnlyEvents")
            after = arguments.get("after")

            result = await client.get_safety_events_by_id(
                safety_event_ids=safety_event_ids,
                include_asset=include_asset,
                include_driver=include_driver,
                include_vg_only_events=include_vg_only_events,
                after=after,
            )
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_trips":
        try:
            # Extract parameters from arguments
            ids = arguments.get("ids")
            start_time = arguments.get("startTime")
            end_time = arguments.get("endTime")
            query_by = arguments.get("queryBy")
            completion_status = arguments.get("completionStatus")
            include_asset = arguments.get("includeAsset")
            after = arguments.get("after")

            # Validate required parameter
            if not ids:
                return [TextContent(
                    type="text",
                    text="Error: 'ids' parameter is required. Use list_vehicles to find asset IDs."
                )]

            # Default behavior: when no start time specified, default to 7 days ago
            # with includeAsset=true for context
            if start_time is None:
                now = datetime.now(timezone.utc)
                start_time = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

            if include_asset is None:
                include_asset = True

            # Call the Samsara API
            result = await client.get_trips(
                ids=ids,
                start_time=start_time,
                end_time=end_time,
                query_by=query_by,
                completion_status=completion_status,
                include_asset=include_asset,
                after=after,
            )

            # Return the result as JSON text
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_drivers":
        try:
            driver_activation_status = arguments.get("driverActivationStatus")
            limit = arguments.get("limit")
            after = arguments.get("after")
            parent_tag_ids = arguments.get("parentTagIds")
            tag_ids = arguments.get("tagIds")
            attribute_value_ids = arguments.get("attributeValueIds")
            attributes = arguments.get("attributes")
            updated_after_time = arguments.get("updatedAfterTime")
            created_after_time = arguments.get("createdAfterTime")

            result = await client.list_drivers(
                driver_activation_status=driver_activation_status,
                limit=limit,
                after=after,
                parent_tag_ids=parent_tag_ids,
                tag_ids=tag_ids,
                attribute_value_ids=attribute_value_ids,
                attributes=attributes,
                updated_after_time=updated_after_time,
                created_after_time=created_after_time,
            )

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "create_driver":
        try:
            # Build driver body from tool arguments (required: name, username, password)
            name = arguments.get("name")
            username = arguments.get("username")
            password = arguments.get("password")

            if not name or not username or not password:
                return [TextContent(
                    type="text",
                    text="Error: create_driver requires 'name', 'username', and 'password'."
                )]

            driver: dict[str, Any] = {
                "name": name,
                "username": username,
                "password": password,
            }

            # Optional fields - only include if provided
            if arguments.get("licenseNumber") is not None:
                driver["licenseNumber"] = arguments["licenseNumber"]
            if arguments.get("licenseState") is not None:
                driver["licenseState"] = arguments["licenseState"]
            if arguments.get("phone") is not None:
                driver["phone"] = arguments["phone"]
            if arguments.get("notes") is not None:
                driver["notes"] = arguments["notes"]
            if arguments.get("tagIds") is not None:
                driver["tagIds"] = arguments["tagIds"]
            if arguments.get("timezone") is not None:
                driver["timezone"] = arguments["timezone"]
            if arguments.get("externalIds") is not None:
                driver["externalIds"] = arguments["externalIds"]
            if arguments.get("locale") is not None:
                driver["locale"] = arguments["locale"]
            if arguments.get("eldExempt") is not None:
                driver["eldExempt"] = arguments["eldExempt"]
            if arguments.get("eldExemptReason") is not None:
                driver["eldExemptReason"] = arguments["eldExemptReason"]
            if arguments.get("vehicleGroupTagId") is not None:
                driver["vehicleGroupTagId"] = arguments["vehicleGroupTagId"]
            if arguments.get("staticAssignedVehicleId") is not None:
                driver["staticAssignedVehicleId"] = arguments["staticAssignedVehicleId"]

            result = await client.create_driver(driver)

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_driver":
        try:
            id = arguments.get("id")
            if not id:
                return [TextContent(
                    type="text",
                    text="Error: get_driver requires 'id'."
                )]
            result = await client.get_driver(id=id)
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "update_driver":
        try:
            id = arguments.get("id")
            body = arguments.get("body") or {}
            if not id:
                return [TextContent(
                    type="text",
                    text="Error: update_driver requires 'id'."
                )]
            result = await client.update_driver(id=id, driver=body)
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "list_gateways":
        try:
            models = arguments.get("models")
            after = arguments.get("after")
            result = await client.list_gateways(models=models, after=after)
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "list_tags":
        try:
            limit = arguments.get("limit")
            after = arguments.get("after")

            result = await client.list_tags(
                limit=limit,
                after=after,
            )

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "create_tag":
        try:
            tag_name = arguments.get("name")
            if not tag_name:
                return [TextContent(
                    type="text",
                    text="Error: 'name' is required to create a tag."
                )]

            body = {"name": tag_name}
            if arguments.get("parentTagId"):
                body["parentTagId"] = arguments["parentTagId"]

            result = await client.create_tag(body)
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_speeding_intervals":
        try:
            asset_ids = arguments.get("assetIds")
            start_time = arguments.get("startTime")
            end_time = arguments.get("endTime")
            query_by = arguments.get("queryBy")
            include_asset = arguments.get("includeAsset")
            include_driver_id = arguments.get("includeDriverId")
            after = arguments.get("after")
            severity_levels = arguments.get("severityLevels")

            if not asset_ids or not start_time:
                return [TextContent(
                    type="text",
                    text="Error: get_speeding_intervals requires 'assetIds' and 'startTime'."
                )]

            result = await client.get_speeding_intervals(
                asset_ids=asset_ids,
                start_time=start_time,
                end_time=end_time,
                query_by=query_by,
                include_asset=include_asset,
                include_driver_id=include_driver_id,
                after=after,
                severity_levels=severity_levels,
            )

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_safety_settings":
        try:
            result = await client.get_safety_settings()

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    elif name == "get_org_info":
        try:
            result = await client.get_organization_info()
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\n\nPlease wait {e.retry_after} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\n\nResponse details: {json.dumps(e.response_body, indent=2)}"
            return [TextContent(type="text", text=f"Error: {error_message}")]
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {type(e).__name__}: {str(e)}"
            )]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Main entry point for the MCP server."""
    # Fail fast at startup if API token is missing
    try:
        # Initialize the Samsara client at startup
        get_samsara_client()
    except ValueError as e:
        # Missing API token - fail fast with clear error message
        print(f"ERROR: {str(e)}", file=sys.stderr)
        print(
            "\nPlease set the SAMSARA_API_TOKEN environment variable before starting the server.",
            file=sys.stderr
        )
        sys.exit(1)
    except Exception as e:
        # Any other initialization error
        print(f"ERROR: Failed to initialize Samsara client: {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())

