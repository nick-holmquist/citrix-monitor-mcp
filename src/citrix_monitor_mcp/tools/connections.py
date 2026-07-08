"""Connection-related tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return connection-related tools."""
    return [
        Tool(
            name="citrix_connection_list",
            description="List connections (initial connects and reconnects)",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_key": {
                        "type": "string",
                        "description": "Filter by session key",
                    },
                    "filter": {
                        "type": "string",
                        "description": "Custom OData filter expression",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_connection_failures",
            description=(
                "Get connection failure logs. ConnectionFailureLogs has no DesktopGroup "
                "navigation property, so delivery-group filtering isn't available here — "
                "pass a custom filter against Machine/User/Session if you need to scope "
                "by delivery group via one of those."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7,
                    },
                    "filter": {
                        "type": "string",
                        "description": "Custom OData filter expression",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_failure_summary",
            description="Get failure summary counts by time period",
            inputSchema={
                "type": "object",
                "properties": {
                    "delivery_group": {
                        "type": "string",
                        "description": "Filter by delivery group name",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_connection_failure_categories",
            description="List connection failure category lookup values",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Handle connection tool calls."""
    client = get_client()

    if name == "citrix_connection_list":
        return client.list_connections(
            filter=arguments.get("filter"),
            session_key=arguments.get("session_key"),
        )

    elif name == "citrix_connection_failures":
        return client.get_connection_failures(
            filter=arguments.get("filter"),
            days=arguments.get("days", 7),
        )

    elif name == "citrix_failure_summary":
        return client.get_failure_summary(
            delivery_group=arguments.get("delivery_group"),
            days=arguments.get("days", 7),
        )

    elif name == "citrix_connection_failure_categories":
        return client.list_connection_failure_categories()

    else:
        raise ValueError(f"Unknown tool: {name}")
