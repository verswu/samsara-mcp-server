# Samsara MCP Server

An MCP (Model Context Protocol) server for integrating with the Samsara Fleet API.

## Features

- **list_vehicles** - List vehicles from your Samsara fleet with filtering by tags, attributes, and time ranges
- **get_vehicle** - Retrieve a single vehicle by ID (Samsara ID or external ID, e.g. samsara.vin:...)
- **update_vehicle** - Update a vehicle by ID (pass only fields to patch)
- **get_asset_locations** - Get real-time GPS location and speed data for assets with optional street addresses
- **get_safety_events** - Retrieve safety events like harsh braking, speeding, collisions, drowsiness, and seatbelt violations
- **get_safety_events_by_id** - Get details for specified safety events by ID (UUIDs); use get_safety_events first to get IDs (5 req/sec)
- **get_trips** - Get trip history with start/end locations, duration, and distance
- **get_drivers** - List all drivers in the organization with filtering by status, tags, and time ranges
- **create_driver** - Create a new driver (name, username, password required; optional license, phone, notes, tags, etc.)
- **list_gateways** - List all gateways with optional filter by models and pagination (5 req/sec; Read Gateways scope)
- **get_org_info** - Get information about your organization (no parameters)
- Comprehensive error handling for rate limits and API errors
- Fail-fast startup validation

## LLM Client Compatibility

| LLM Client | Transport | Status |
|------------|-----------|--------|
| Claude Desktop | stdio | ✅ Supported |
| Gemini CLI | stdio | ✅ Supported |
| OpenAI Codex CLI | stdio | ✅ Supported |
| ChatGPT | HTTP/SSE | ❌ Not yet supported |

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Samsara API token

### Installation

1. Clone this repository:
```bash
cd samsara-mcp-server
```

2. Install dependencies:
```bash
uv sync
```

3. Set your Samsara API token using one of these methods:

**Option A: Using a `.env` file (recommended)**

Create a `.env` file in the project root:
```bash
SAMSARA_API_TOKEN=your-api-token-here
```

**Option B: Environment variable**
```bash
export SAMSARA_API_TOKEN="your-api-token-here"
```

## Available Tools

### list_vehicles

List all vehicles from the Samsara fleet with optional filtering.

**Parameters:**
- `limit` - Number of results (1-512, default 512)
- `after` - Pagination cursor
- `parentTagIds` - Filter by parent tag IDs (comma-separated)
- `tagIds` - Filter by tag IDs (comma-separated)
- `attributeValueIds` - Filter by attribute value IDs (comma-separated)
- `attributes` - Filter by attribute name-value pairs
- `updatedAfterTime` - Filter by update time (RFC 3339)
- `createdAfterTime` - Filter by creation time (RFC 3339)

### get_vehicle

Retrieve a single vehicle by ID.

**Parameters:**
- `id` - **Required.** Samsara vehicle ID or external ID in `key:value` format (e.g. `maintenanceId:250020`, `samsara.vin:1HGBH41JXMN109186`).

**Scope:** Read Vehicles

### update_vehicle

Update a vehicle by ID. Only include fields you wish to change (no required body fields).

**Parameters:**
- `id` - **Required.** Samsara vehicle ID or external ID in `key:value` format.
- `body` - **Required.** Object with fields to update (UpdateVehicleRequest), e.g. name, notes, tagIds.

**Scope:** Write Vehicles

### get_asset_locations

Get current location and speed data for assets. Returns GPS coordinates, optional street addresses, and speed.

**Parameters:**
- `startTime` - Start time in RFC 3339 format
- `endTime` - End time in RFC 3339 format
- `ids` - Comma-separated list of asset IDs
- `includeSpeed` - Include speed data (default: true)
- `includeReverseGeo` - Include street address (default: true)
- `includeGeofenceLookup` - Include geofence information
- `includeHighFrequencyLocations` - Include high frequency location data
- `includeExternalIds` - Include external IDs
- `limit` - Number of results (1-512)
- `after` - Pagination cursor

**Default behavior:** When no time range is specified, returns the last 5 minutes of data with `includeReverseGeo=true` and `includeSpeed=true`.

### get_safety_events

Get safety events like harsh braking, speeding, collisions, drowsiness, mobile usage, and seatbelt violations.

**Parameters:**
- `startTime` - Start time in RFC 3339 format
- `endTime` - End time in RFC 3339 format
- `queryByTimeField` - Query by `updatedAtTime` or `createdAtTime`
- `assetIds` - Comma-separated asset IDs
- `driverIds` - Comma-separated driver IDs
- `tagIds` - Comma-separated tag IDs
- `assignedCoaches` - Comma-separated coach IDs
- `behaviorLabels` - Filter by behavior type: `Acceleration`, `Braking`, `Crash`, `Speeding`, `HarshTurn`, `FollowingDistance`, `LaneDeparture`, `Drowsy`, `MobileUsage`, `NoSeatbelt`, `RanRedLight`, `RollingStop`, etc.
- `eventStates` - Filter by state: `needsReview`, `reviewed`, `needsCoaching`, `coached`, `dismissed`, `needsRecognition`, `recognized`
- `includeAsset` - Include asset details (default: true)
- `includeDriver` - Include driver details (default: true)
- `includeVgOnlyEvents` - Include video-only events
- `after` - Pagination cursor

**Default behavior:** When no `startTime` is specified, returns events from the last 7 days with `includeDriver=true` and `includeAsset=true`.

### get_safety_events_by_id

Get details for specified safety events by ID. Use **get_safety_events** (stream) first to discover event IDs. Rate limit: 5 requests/sec.

**Parameters:**
- `safetyEventIds` - **Required.** Array of safety event IDs (Samsara UUIDs).
- `includeAsset` - Include expanded asset data (default: false).
- `includeDriver` - Include expanded driver data (default: false).
- `includeVgOnlyEvents` - Include events from devices with only a Vehicle Gateway (VG) (default: false).
- `after` - Pagination cursor from previous response.

**Scope:** Read Safety Events & Scores (Safety & Cameras)

### get_trips

Get trip history for specific vehicles. Returns trip start/end times, locations, distance, and duration.

**Parameters:**
- `ids` - Comma-separated list of asset IDs (up to 50, **required**)
- `startTime` - Start time in RFC 3339 format
- `endTime` - End time in RFC 3339 format
- `queryBy` - Query by `updatedAtTime` or `tripStartTime`
- `completionStatus` - Filter by `inProgress`, `completed`, or `all`
- `includeAsset` - Include asset details (default: true)
- `after` - Pagination cursor

**Default behavior:** When no `startTime` is specified, returns trips from the last 7 days with `includeAsset=true`. Note: `ids` is required - use `list_vehicles` first to find asset IDs if you only have vehicle names.

### get_drivers

List all drivers in the organization. Supports active/deactivated status and filtering by tags and time ranges.

**Parameters:**
- `driverActivationStatus` - `active` (default) or `deactivated`
- `limit` - Number of results (1-512)
- `after` - Pagination cursor
- `parentTagIds` - Comma-separated parent tag IDs
- `tagIds` - Comma-separated tag IDs
- `attributeValueIds` - Comma-separated attribute value IDs
- `attributes` - Filter by attribute name-value or range
- `updatedAfterTime` - Filter by updated time (RFC 3339)
- `createdAfterTime` - Filter by created time (RFC 3339)

**Scope:** Read Drivers

### create_driver

Create a new driver in the organization.

**Parameters (required):**
- `name` - Driver's full name
- `username` - Login username for the driver app (unique, no spaces or `@`)
- `password` - Password for the driver app

**Parameters (optional):**
- `licenseNumber`, `licenseState` - License info
- `phone`, `notes` - Contact and notes
- `tagIds` - Tag IDs (required if API access is scoped by tags)
- `timezone` - IANA timezone (e.g. `America/Los_Angeles`)
- `externalIds` - External IDs (e.g. payrollId, maintenanceId)
- `locale`, `eldExempt`, `eldExemptReason`, `vehicleGroupTagId`, `staticAssignedVehicleId`

**Scope:** Write Drivers

### list_gateways

List all gateways. Optional filter by gateway models and pagination cursor. Rate limit: 5 requests/sec.

**Parameters:**
- `models` - Filter by gateway models (array of strings)
- `after` - Pagination cursor from the previous page of results

**Scope:** Read Gateways (Setup & Administration)

### get_org_info

Get information about your organization (e.g. org name, ID, settings). No parameters required.

**Scope:** Read Org Information (Setup & Administration)

## Testing Locally

### Run the Test Script

```bash
# Using .env file (recommended)
uv run python test_server.py

# Or with environment variable
SAMSARA_API_TOKEN="your-api-token-here" uv run python test_server.py
```

### Pytest (unit tests)

Unit and tool-registration tests live in `tests/`. No real API calls—all HTTP is mocked.

```bash
uv sync --group dev   # install pytest, pytest-asyncio
uv run pytest tests/ -v
```

### Manual Testing

```bash
uv run python server.py
```

The server uses stdio transport, so it will wait for MCP protocol messages on stdin.

## LLM Client Setup

### Claude Desktop

**Configuration file location:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Configuration snippet:**

Add this to the `mcpServers` section of your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "samsara": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/samsara-mcp-server",
        "python",
        "server.py"
      ],
      "env": {
        "SAMSARA_API_TOKEN": "your-samsara-api-token-here"
      }
    }
  }
}
```

**Notes:**
- Replace `/path/to/samsara-mcp-server` with your actual project path
- On macOS, you may need the full path to `uv` (run `which uv` to find it)
- Restart Claude Desktop after updating the config

---

### Gemini CLI

**Install:**
```bash
npm install -g @google/gemini-cli
```

**Configuration file location:** `~/.gemini/settings.json`

**Configuration snippet:**

```json
{
  "mcpServers": {
    "samsara": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/samsara-mcp-server", "python", "server.py"]
    }
  }
}
```

**Notes:**
- Replace `/path/to/samsara-mcp-server` with your actual project path
- Set `SAMSARA_API_TOKEN` in your environment or `.env` file (server loads it automatically via python-dotenv)
- Run `gemini` to start chatting

---

### OpenAI Codex CLI

**Configuration file location:** `~/.codex/config.toml`

**Configuration snippet:**

```toml
[mcp_servers.samsara]
command = "uv"
args = ["run", "--directory", "/path/to/samsara-mcp-server", "python", "server.py"]

[mcp_servers.samsara.env]
SAMSARA_API_TOKEN = "your-token-here"
```

**Notes:**
- Replace `/path/to/samsara-mcp-server` with your actual project path
- Restart Codex CLI after updating the config

---

### ChatGPT

**Status:** Not currently supported

ChatGPT requires a remote HTTP server (SSE transport), not local stdio. This server currently only supports stdio transport for local use.

HTTP transport support is planned for a future release. See [Development](#development) for contribution guidelines.

---

## Example Prompts

Once configured, you can ask your LLM to use the Samsara tools:

- "List all vehicles in my fleet"
- "Show me vehicles with tag ID 1234"
- "Get vehicle by ID 281474976712793" / "Show me vehicle with VIN 1HGBH41JXMN109186"
- "Update vehicle 281474976712793 name to Truck 2"
- "Where are my assets right now?"
- "Get the location of asset ID 12345"
- "Show me safety events from the last week"
- "What harsh braking events happened today?"
- "Show me all speeding events that need review"
- "Get details for safety event IDs evt-uuid-1 and evt-uuid-2" / "Get safety events by ID evt-uuid-1"
- "Show me trips for vehicle 12345 from the last week"
- "What trips are currently in progress?"
- "How many miles did vehicle X drive yesterday?"
- "List all drivers" / "Show me deactivated drivers"
- "Create a new driver named Jane Doe with username janedoe"
- "List all gateways" / "Show gateways by model AG24"
- "What's my organization name?" / "Get my org info"

## API Rate Limits

The Samsara API has a rate limit of 25 requests per second. The server handles rate limit errors (429) gracefully and will inform you when you need to wait before retrying.

## Error Handling

The server includes comprehensive error handling:

- **Missing API Token**: Fails fast at startup with a clear error message
- **HTTP Errors**: Returns user-friendly error messages with details from the API
- **Rate Limiting**: Specifically handles 429 responses with retry information
- **Network Errors**: Handles connection issues gracefully

## Development

### Project Structure

```
samsara-mcp-server/
├── server.py              # MCP server implementation
├── samsara_client.py      # Samsara API client
├── test_server.py         # Manual test script (MCP Inspector / live API)
├── pyproject.toml         # Project dependencies and pytest config
├── .env                   # Environment variables (create this)
├── tests/                 # Pytest unit and tool-registration tests
│   ├── conftest.py        # Shared fixtures (mock client, sample responses)
│   ├── test_samsara_client.py   # API client unit tests (mocked HTTP)
│   └── test_server.py     # MCP tool registration tests
├── CURSOR_CONTEXT.md      # Pattern for adding new endpoints
├── scripts/
│   └── add_endpoint.py    # Codegen: OpenAPI spec → client + tool + test stub
└── README.md              # This file
```

### Adding New Tools

To add new Samsara API endpoints as tools:

1. Add a method to `SamsaraClient` in `samsara_client.py`
2. Register the tool in `server.py` using `@server.list_tools()` (name, description, `inputSchema`)
3. Handle the tool call in `@server.call_tool()`

See **CURSOR_CONTEXT.md** for the full pattern, API conventions (RFC 3339 times, pagination with `after`), and default behaviors. Add unit tests in `tests/test_samsara_client.py` (mocked HTTP) and `tests/test_server.py` (tool registration).

**Codegen script:** `scripts/add_endpoint.py` takes an OpenAPI endpoint spec (JSON from stdin or file) and prints a client method, tool registration, call_tool handler, and test stub for copy-paste:

```bash
echo '{"path": "/me", "get": {"operationId": "getOrganizationInfo", "summary": "Get org info"}}' | python scripts/add_endpoint.py
python scripts/add_endpoint.py path/to/spec.json
```

## License

[Add your license here]
