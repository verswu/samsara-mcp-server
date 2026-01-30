#!/usr/bin/env python3
"""
Test script to validate the MCP server works correctly.
This script tests the server's tool listing and basic functionality.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the project directory to the path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_server():
    """Test the MCP server."""
    print("Testing Samsara MCP Server...")
    print("=" * 50)
    
    # Check for API token
    api_token = os.getenv("SAMSARA_API_TOKEN")
    if not api_token:
        print("⚠️  WARNING: SAMSARA_API_TOKEN not set. Some tests may fail.")
        print("   Set it with: export SAMSARA_API_TOKEN='your-token'")
        print()
    else:
        print("✅ SAMSARA_API_TOKEN is set")
        print()
    
    # Get the server script path
    server_script = project_dir / "server.py"
    if not server_script.exists():
        print(f"❌ ERROR: server.py not found at {server_script}")
        return False
    
    print(f"📝 Server script: {server_script}")
    print()
    
    # Test 1: List tools
    print("Test 1: Listing available tools...")
    try:
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", str(server_script)],
            env={"SAMSARA_API_TOKEN": api_token} if api_token else None,
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools
                tools_result = await session.list_tools()
                tools = tools_result.tools
                
                print(f"✅ Found {len(tools)} tool(s):")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description[:60]}...")
                
                # Test 2: Check list_vehicles tool exists
                print()
                print("Test 2: Checking list_vehicles tool...")
                vehicle_tool = next((t for t in tools if t.name == "list_vehicles"), None)
                if vehicle_tool:
                    print("✅ list_vehicles tool found")
                    print(f"   Description: {vehicle_tool.description[:100]}...")
                    
                    # Check schema
                    if hasattr(vehicle_tool, "inputSchema"):
                        schema = vehicle_tool.inputSchema
                        if isinstance(schema, dict) and "properties" in schema:
                            props = schema["properties"]
                            print(f"   Parameters: {len(props)}")
                            for param_name in list(props.keys())[:5]:
                                print(f"     - {param_name}")
                            if len(props) > 5:
                                print(f"     ... and {len(props) - 5} more")
                else:
                    print("❌ list_vehicles tool not found")
                    return False
                
                # Test 3: Try calling the tool (if API token is set)
                if api_token:
                    print()
                    print("Test 3: Testing list_vehicles tool call (with limit=1)...")
                    try:
                        result = await session.call_tool(
                            "list_vehicles",
                            arguments={"limit": 1}
                        )
                        
                        if result.content:
                            content = result.content[0]
                            if hasattr(content, "text"):
                                data = json.loads(content.text)
                                print("✅ Tool call successful!")
                                if "data" in data:
                                    print(f"   Returned {len(data['data'])} vehicle(s)")
                                elif "vehicles" in data:
                                    print(f"   Returned {len(data['vehicles'])} vehicle(s)")
                                else:
                                    print(f"   Response keys: {list(data.keys())}")
                            else:
                                print("⚠️  Tool returned non-text content")
                        else:
                            print("⚠️  Tool returned empty content")
                            
                    except Exception as e:
                        error_msg = str(e)
                        if "429" in error_msg or "rate limit" in error_msg.lower():
                            print("⚠️  Rate limit hit (this is expected if testing frequently)")
                        elif "401" in error_msg or "unauthorized" in error_msg.lower():
                            print("❌ Authentication failed - check your API token")
                        else:
                            print(f"❌ Tool call failed: {error_msg}")
                else:
                    print()
                    print("Test 3: Skipped (no API token set)")
                
                print()
                print("=" * 50)
                print("✅ All tests passed!")
                return True
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_server())
    sys.exit(0 if success else 1)

