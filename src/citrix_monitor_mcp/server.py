"""Citrix Monitor MCP Server."""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .tools import machines, sessions, connections, applications, users, analytics


server = Server("citrix-monitor-mcp")


def format_result(result: Any) -> str:
    """Format result as JSON string."""
    return json.dumps(result, indent=2, default=str)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    tools = []
    tools.extend(machines.get_tools())
    tools.extend(sessions.get_tools())
    tools.extend(connections.get_tools())
    tools.extend(applications.get_tools())
    tools.extend(users.get_tools())
    tools.extend(analytics.get_tools())
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = None

        # Route to appropriate handler based on tool name prefix
        if name.startswith("citrix_machine"):
            result = machines.handle_tool(name, arguments)
        elif name.startswith("citrix_session"):
            result = sessions.handle_tool(name, arguments)
        elif name.startswith("citrix_connection") or name.startswith("citrix_failure"):
            result = connections.handle_tool(name, arguments)
        elif name.startswith("citrix_app"):
            result = applications.handle_tool(name, arguments)
        elif name.startswith("citrix_user"):
            result = users.handle_tool(name, arguments)
        else:
            # Analytics and other tools
            result = analytics.handle_tool(name, arguments)

        return [TextContent(type="text", text=format_result(result))]

    except Exception as e:
        return [TextContent(type="text", text=format_result({"error": str(e)}))]


async def run_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Entry point."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
