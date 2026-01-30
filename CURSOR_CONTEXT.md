# Samsara MCP Server - Project Context

## Overview

This is an MCP (Model Context Protocol) server that connects LLMs (Claude, Gemini, ChatGPT) to the Samsara Fleet API. It allows users to ask natural language questions about their fleet data.

**Goal:** Build an open-source tool that the SE team (and eventually external users) can use to query Samsara data conversationally.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              samsara_client.py                      │
│         (Samsara API wrapper - async httpx)         │
└─────────────────────────────────────────────────────┘
                        ↑
┌─────────────────────────────────────────────────────┐
│                   server.py                         │
│         (MCP server - stdio transport)              │
│         - Registers tools                           │
│         - Handles tool calls                        │
│         - Returns results to LLM                    │
└─────────────────────────────────────────────────────┘
```

## Current Tools Implemented

| Tool | Endpoint | Description |
|------|----------|-------------|
| `list_vehicles` | `GET /fleet/vehicles` | List all vehicles with filtering |
| `get_asset_locations` | `GET /assets/location-and-speed/stream` | Real-time GPS location and speed |
| `get_safety_events` | `GET /safety-events/stream` | Harsh braking, speeding, collisions, etc. |
| `get_trips` | `GET /trips/stream` | Trip history with start/end locations |

## Tech Stack

- **Python 3.13+**
- **uv** - Package manager
- **mcp** - MCP SDK for Python
- **httpx** - Async HTTP client
- **python-dotenv** - Environment variable loading

## Project Structure

```
samsara-mcp-server/
├── server.py              # MCP server - tool registration and handling
├── samsara_client.py      # Samsara API client wrapper
├── test_server.py         # Test script
├── pyproject.toml         # Dependencies
├── .env                   # SAMSARA_API_TOKEN (not committed)
└── README.md              # User-facing documentation
```

## Pattern for Adding New Endpoints

### 1. Add method to `samsara_client.py`

```python
async def new_endpoint(
    self,
    required_param: str,
    optional_param: Optional[str] = None,
) -> dict:
    """
    Description of what this endpoint does.
    
    Args:
        required_param: What this param does
        optional_param: What this param does
        
    Returns:
        API response with data array and pagination info
    """
    params = {"requiredParam": required_param}
    
    if optional_param:
        params["optionalParam"] = optional_param
    
    return await self._request("GET", "/endpoint/path", params=params)
```

### 2. Register tool in `server.py`

Add to `@server.list_tools()`:

```python
types.Tool(
    name="tool_name",
    description="Description that helps the LLM understand when to use this tool. Be specific about what data it returns and any requirements.",
    inputSchema={
        "type": "object",
        "properties": {
            "required_param": {
                "type": "string",
                "description": "What this param does"
            },
            "optional_param": {
                "type": "string", 
                "description": "What this param does"
            }
        },
        "required": ["required_param"]
    }
)
```

### 3. Handle tool call in `server.py`

Add to `@server.call_tool()`:

```python
elif name == "tool_name":
    result = await client.new_endpoint(
        required_param=arguments["required_param"],
        optional_param=arguments.get("optional_param"),
    )
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
```

## API Conventions

- **Base URL:** `https://api.samsara.com`
- **Auth:** Bearer token in header
- **Time format:** RFC 3339 (e.g., `2025-01-15T00:00:00Z`)
- **Pagination:** Uses `after` cursor from `pagination.endCursor` in response
- **Rate limits:** Vary by endpoint (5-25 req/sec)

## Default Behaviors

When implementing tools, add sensible defaults:

- **Time range:** Default to last 7 days if not specified
- **Include flags:** Set `includeDriver=true`, `includeAsset=true` when available so LLM gets useful context
- **Limit:** Use reasonable defaults (e.g., 100) to avoid huge responses

## Testing

### MCP Inspector (recommended for development)
```bash
npx @modelcontextprotocol/inspector uv run python server.py
```

### Test script
```bash
uv run python test_server.py
```

### Claude Desktop
Config location: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "samsara": {
      "command": "/path/to/uv",
      "args": ["run", "--directory", "/path/to/samsara-mcp-server", "python", "server.py"],
      "env": {
        "SAMSARA_API_TOKEN": "your-token"
      }
    }
  }
}
```

### Gemini CLI
Config location: `~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "samsara": {
      "command": "uv",
      "args": ["run", "python", "/path/to/server.py"]
    }
  }
}
```

## Future Endpoints to Add

Priority endpoints based on common use cases:

| Endpoint | Use Case |
|----------|----------|
| `GET /fleet/drivers` | List drivers, get driver details |
| `GET /fleet/vehicles/stats` | Odometer, fuel, engine hours |
| `GET /fleet/hos/logs` | Hours of service / ELD data |
| `GET /addresses` | Geofences and addresses |
| `GET /fleet/reports/fuel-energy` | Fuel consumption reports |

## OpenAPI Spec Location

Full spec: https://developers.samsara.com/openapi/samsara-api.json

When adding endpoints, extract the relevant section from the spec and include it in your prompt.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SAMSARA_API_TOKEN` | Samsara API token with appropriate scopes |

The server loads `.env` automatically via `python-dotenv`.

## LLM Compatibility

| Client | Transport | Status |
|--------|-----------|--------|
| Claude Desktop | stdio | ✅ Working |
| Gemini CLI | stdio | ✅ Working |
| ChatGPT | HTTP/SSE | ❌ Needs remote hosting |
| OpenAI Codex | stdio | ✅ Should work |

## Future Plans

1. **More endpoints** - Expand API coverage
2. **HTTP transport** - Enable ChatGPT support and hosted version
3. **"Ask Samsara" web app** - Hosted version where SE team controls config
4. **Open source release** - PyPI package, documentation, examples
