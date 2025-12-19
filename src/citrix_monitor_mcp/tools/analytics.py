"""Analytics and infrastructure tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return analytics and infrastructure tools."""
    return [
        Tool(
            name="citrix_query_raw",
            description="Execute a custom OData query against any entity",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name (e.g., Machines, Sessions, Connections)",
                    },
                    "filter": {
                        "type": "string",
                        "description": "OData $filter expression",
                    },
                    "select": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to select",
                    },
                    "orderby": {
                        "type": "string",
                        "description": "OData $orderby expression",
                    },
                    "top": {
                        "type": "integer",
                        "description": "Maximum records to return",
                    },
                    "expand": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Related entities to expand",
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="citrix_delivery_groups",
            description="List all delivery groups",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="citrix_hypervisors",
            description="List all hypervisors/hosts",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="citrix_load_index",
            description="Get load index data for machines",
            inputSchema={
                "type": "object",
                "properties": {
                    "machine_id": {
                        "type": "integer",
                        "description": "Machine ID",
                    },
                    "machine_name": {
                        "type": "string",
                        "description": "Machine name (alternative to machine_id)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_entity_count",
            description="Get count of entities matching a filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name (e.g., Machines, Sessions)",
                    },
                    "filter": {
                        "type": "string",
                        "description": "OData $filter expression",
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="citrix_aggregate",
            description="Execute an OData aggregation query",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name",
                    },
                    "apply": {
                        "type": "string",
                        "description": "OData $apply expression (e.g., 'aggregate(SessionCount with sum as Total)')",
                    },
                },
                "required": ["entity", "apply"],
            },
        ),
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Handle analytics tool calls."""
    client = get_client()

    if name == "citrix_query_raw":
        entity = arguments.get("entity")
        if not entity:
            raise ValueError("entity is required")

        return client.query(
            entity=entity,
            filter=arguments.get("filter"),
            select=arguments.get("select"),
            orderby=arguments.get("orderby"),
            top=arguments.get("top"),
            expand=arguments.get("expand"),
        )

    elif name == "citrix_delivery_groups":
        return client.list_delivery_groups()

    elif name == "citrix_hypervisors":
        return client.list_hypervisors()

    elif name == "citrix_load_index":
        return client.get_load_indexes(
            machine_id=arguments.get("machine_id"),
            machine_name=arguments.get("machine_name"),
        )

    elif name == "citrix_entity_count":
        entity = arguments.get("entity")
        if not entity:
            raise ValueError("entity is required")
        return {"entity": entity, "count": client.get_count(entity, filter=arguments.get("filter"))}

    elif name == "citrix_aggregate":
        entity = arguments.get("entity")
        apply = arguments.get("apply")
        if not entity or not apply:
            raise ValueError("entity and apply are required")
        return client.aggregate(entity, apply)

    else:
        raise ValueError(f"Unknown tool: {name}")
