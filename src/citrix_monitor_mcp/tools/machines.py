"""Machine-related tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return machine-related tools."""
    return [
        Tool(
            name="citrix_machine_list",
            description="List all machines (VDAs) with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "registration_state": {
                        "type": "string",
                        "description": "Filter by registration state",
                        "enum": ["Registered", "Unregistered", "Unknown"],
                    },
                    "power_state": {
                        "type": "string",
                        "description": "Filter by power state",
                        "enum": [
                            "Unknown",
                            "Unavailable",
                            "Off",
                            "On",
                            "Suspended",
                            "TurningOn",
                            "TurningOff",
                            "Suspending",
                            "Resuming",
                            "Unmanaged",
                            "NotSupported",
                            "VirtualMachineNotFound",
                        ],
                    },
                    "in_maintenance": {
                        "type": "boolean",
                        "description": "Filter by maintenance mode",
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
            name="citrix_machine_status",
            description="Get detailed status for a specific machine by ID or name",
            inputSchema={
                "type": "object",
                "properties": {
                    "machine_id": {
                        "type": "string",
                        "description": "Machine ID (GUID, e.g. '31a02fb0-b673-4520-b94d-017fa2acd3b8')",
                    },
                    "name": {
                        "type": "string",
                        "description": "Machine name (alternative to machine_id)",
                    },
                },
                "required": [],
                "anyOf": [{"required": ["machine_id"]}, {"required": ["name"]}],
            },
        ),
        Tool(
            name="citrix_machine_metrics",
            description="Get CPU and memory usage metrics for a machine",
            inputSchema={
                "type": "object",
                "properties": {
                    "machine_id": {
                        "type": "string",
                        "description": "Machine ID (GUID, e.g. '31a02fb0-b673-4520-b94d-017fa2acd3b8')",
                    },
                    "name": {
                        "type": "string",
                        "description": "Machine name (alternative to machine_id)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_machine_failures",
            description="Get failure logs for a specific machine",
            inputSchema={
                "type": "object",
                "properties": {
                    "machine_id": {
                        "type": "string",
                        "description": "Machine ID (GUID, e.g. '31a02fb0-b673-4520-b94d-017fa2acd3b8')",
                    },
                    "name": {
                        "type": "string",
                        "description": "Machine name (alternative to machine_id)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_catalog_list",
            description="List machine catalogs in the Site",
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
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Handle machine tool calls."""
    client = get_client()

    if name == "citrix_machine_list":
        return client.list_machines(
            filter=arguments.get("filter"),
            registration_state=arguments.get("registration_state"),
            power_state=arguments.get("power_state"),
            in_maintenance=arguments.get("in_maintenance"),
        )

    elif name == "citrix_machine_status":
        machine_id = arguments.get("machine_id")
        name_arg = arguments.get("name")

        if machine_id:
            return client.get_machine(machine_id)
        elif name_arg:
            return client.get_machine_by_name(name_arg)
        else:
            raise ValueError("Either machine_id or name is required")

    elif name == "citrix_machine_metrics":
        return client.get_machine_metrics(
            machine_id=arguments.get("machine_id"),
            name=arguments.get("name"),
        )

    elif name == "citrix_machine_failures":
        return client.get_machine_failures(
            machine_id=arguments.get("machine_id"),
            name=arguments.get("name"),
        )

    elif name == "citrix_catalog_list":
        return client.list_catalogs(filter=arguments.get("filter"))

    else:
        raise ValueError(f"Unknown tool: {name}")
