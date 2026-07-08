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
                        "type": "string",
                        "description": "Application ID (GUID)",
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
            description=(
                "Get application faults (ApplicationFaults entity) — crashes/faults "
                "reported by VDAs. This entity has no Application navigation property; "
                "app_name matches against the process name (ProcessName), not a "
                "published-application display name. For the separate ApplicationErrors "
                "entity (distinct error log), use citrix_app_error_logs instead."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Substring match against ProcessName (e.g. 'notepad')",
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
            name="citrix_app_error_logs",
            description=(
                "Get application error log entries (ApplicationErrors entity, distinct "
                "from citrix_app_errors/ApplicationFaults). No Application navigation "
                "property; app_name matches against ProcessName."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Substring match against ProcessName (e.g. 'notepad')",
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
            name="citrix_app_activity_summary",
            description="Get application usage rollups (launches, usage duration) by time period",
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

    elif name == "citrix_app_error_logs":
        return client.get_application_errors(
            app_name=arguments.get("app_name"),
            days=arguments.get("days", 7),
        )

    elif name == "citrix_app_activity_summary":
        return client.get_application_activity_summary(
            app_name=arguments.get("app_name"),
            days=arguments.get("days", 7),
        )

    else:
        raise ValueError(f"Unknown tool: {name}")
