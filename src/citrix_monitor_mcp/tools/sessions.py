"""Session-related tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return session-related tools."""
    return [
        Tool(
            name="citrix_session_list",
            description="List sessions with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "Only show active sessions (no end date)",
                        "default": False,
                    },
                    "user_name": {
                        "type": "string",
                        "description": "Filter by username",
                    },
                    "machine_name": {
                        "type": "string",
                        "description": "Filter by machine name",
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
            name="citrix_session_details",
            description="Get detailed information for a specific session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_key": {
                        "type": "string",
                        "description": "Session key (GUID)",
                    },
                },
                "required": ["session_key"],
            },
        ),
        Tool(
            name="citrix_session_logon_metrics",
            description="Get logon duration breakdown for a session (GPO, profile, scripts, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_key": {
                        "type": "string",
                        "description": "Session key (GUID)",
                    },
                },
                "required": ["session_key"],
            },
        ),
        Tool(
            name="citrix_session_count",
            description="Get count of sessions matching criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "Only count active sessions",
                        "default": False,
                    },
                    "filter": {
                        "type": "string",
                        "description": "Custom OData filter expression",
                    },
                },
                "required": [],
            },
        ),
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Handle session tool calls."""
    client = get_client()

    if name == "citrix_session_list":
        return client.list_sessions(
            filter=arguments.get("filter"),
            active_only=arguments.get("active_only", False),
            user_name=arguments.get("user_name"),
            machine_name=arguments.get("machine_name"),
        )

    elif name == "citrix_session_details":
        session_key = arguments.get("session_key")
        if not session_key:
            raise ValueError("session_key is required")
        return client.get_session(session_key)

    elif name == "citrix_session_logon_metrics":
        session_key = arguments.get("session_key")
        if not session_key:
            raise ValueError("session_key is required")
        return client.get_logon_metrics(session_key)

    elif name == "citrix_session_count":
        filter_expr = arguments.get("filter")
        if arguments.get("active_only"):
            if filter_expr:
                filter_expr = f"({filter_expr}) and EndDate eq null"
            else:
                filter_expr = "EndDate eq null"
        return {"count": client.get_count("Sessions", filter=filter_expr)}

    else:
        raise ValueError(f"Unknown tool: {name}")
