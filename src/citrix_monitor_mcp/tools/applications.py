"""Application-related tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return application-related tools."""
    return [
        Tool(
            name="citrix_app_list",
            description="List published applications",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Custom OData filter expression",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_app_instances",
            description="List running application instances",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_id": {
                        "type": "integer",
                        "description": "Application ID",
                    },
                    "app_name": {
                        "type": "string",
                        "description": "Application name (alternative to app_id)",
                    },
                    "active_only": {
                        "type": "boolean",
                        "description": "Only show active instances",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_app_errors",
            description="Get application errors and faults",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Filter by application name",
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
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Handle application tool calls."""
    client = get_client()

    if name == "citrix_app_list":
        return client.list_applications(filter=arguments.get("filter"))

    elif name == "citrix_app_instances":
        return client.list_app_instances(
            app_id=arguments.get("app_id"),
            app_name=arguments.get("app_name"),
            active_only=arguments.get("active_only", False),
        )

    elif name == "citrix_app_errors":
        return client.get_app_errors(
            app_name=arguments.get("app_name"),
            days=arguments.get("days", 7),
        )

    else:
        raise ValueError(f"Unknown tool: {name}")
