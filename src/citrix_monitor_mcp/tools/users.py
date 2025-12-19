"""User-related tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return user-related tools."""
    return [
        Tool(
            name="citrix_user_list",
            description="List users in the environment",
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
            name="citrix_user_details",
            description="Get details for a specific user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "User ID",
                    },
                    "username": {
                        "type": "string",
                        "description": "Username (alternative to user_id)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_user_sessions",
            description="Get session history for a specific user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "User ID",
                    },
                    "username": {
                        "type": "string",
                        "description": "Username (alternative to user_id)",
                    },
                },
                "required": [],
            },
        ),
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Handle user tool calls."""
    client = get_client()

    if name == "citrix_user_list":
        return client.list_users(filter=arguments.get("filter"))

    elif name == "citrix_user_details":
        user_id = arguments.get("user_id")
        username = arguments.get("username")

        if user_id:
            return client.get_user(user_id)
        elif username:
            return client.get_user_by_name(username)
        else:
            raise ValueError("Either user_id or username is required")

    elif name == "citrix_user_sessions":
        return client.get_user_sessions(
            user_id=arguments.get("user_id"),
            username=arguments.get("username"),
        )

    else:
        raise ValueError(f"Unknown tool: {name}")
