"""Citrix Monitor MCP Server."""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .tools import (
    machines,
    sessions,
    connections,
    applications,
    users,
    analytics,
    diagnostics,
)


server = Server("citrix-monitor-mcp")

_TOOL_MODULES = (machines, sessions, connections, applications, users, analytics, diagnostics)


def format_result(result: Any) -> str:
    """Format result as JSON string."""
    return json.dumps(result, indent=2, default=str)


def _build_tool_registry() -> dict[str, Any]:
    """Map each tool name to the module that handles it (built once at import)."""
    registry: dict[str, Any] = {}
    for module in _TOOL_MODULES:
        for tool in module.get_tools():
            registry[tool.name] = module
    return registry


_TOOL_REGISTRY = _build_tool_registry()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    tools = []
    for module in _TOOL_MODULES:
        tools.extend(module.get_tools())
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls.

    Handlers perform blocking HTTP I/O (requests + retry sleeps), so they run
    in a worker thread via asyncio.to_thread — otherwise a single slow/rate
    -limited call would stall the event loop and all other MCP traffic.
    Exceptions are intentionally left to propagate: the MCP SDK's call_tool
    wrapper catches them and returns a CallToolResult with isError=True,
    which is the spec-correct way to signal a tool failure.
    """
    module = _TOOL_REGISTRY.get(name)
    if module is None:
        raise ValueError(f"Unknown tool: {name}")

    result = await asyncio.to_thread(module.handle_tool, name, arguments)
    return [TextContent(type="text", text=format_result(result))]


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
