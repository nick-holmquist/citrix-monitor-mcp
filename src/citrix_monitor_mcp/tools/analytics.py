"""Analytics and infrastructure tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return analytics and infrastructure tools."""
    return [
        Tool(
            name="citrix_query_raw",
            description=(
                "Execute a custom OData query against any Monitor Service entity. "
                "Use this for entities without a dedicated tool, or when you need "
                "fields/filters the dedicated tools don't expose. "
                "Example: entity='Sessions', filter=\"LogOnDuration gt 60000 and "
                "StartDate ge 2024-01-01T00:00:00Z\", select=['SessionKey', "
                "'LogOnDuration'], orderby='LogOnDuration desc', top=10. "
                "Date literals must be ISO 8601 UTC (e.g. 2024-01-01T00:00:00Z). "
                "String values are single-quoted; navigation properties use "
                "'Related/Field' syntax (e.g. \"Machine/Name eq 'VDA01'\")."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name (e.g., Machines, Sessions, Connections)",
                    },
                    "filter": {
                        "type": "string",
                        "description": "OData $filter expression, e.g. \"CurrentLoadIndex gt 8000\"",
                    },
                    "select": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to select, e.g. ['Id', 'Name']",
                    },
                    "orderby": {
                        "type": "string",
                        "description": "OData $orderby expression, e.g. 'CreatedDate desc'",
                    },
                    "top": {
                        "type": "integer",
                        "description": "Maximum records to return (per page if paginating)",
                    },
                    "skip": {
                        "type": "integer",
                        "description": "Number of records to skip",
                    },
                    "expand": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Related entities to expand, e.g. ['Machine', 'User']",
                    },
                    "count": {
                        "type": "boolean",
                        "description": "Include total matching count in the response",
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
                        "type": "string",
                        "description": "Machine ID (GUID, e.g. '31a02fb0-b673-4520-b94d-017fa2acd3b8')",
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
        Tool(
            name="citrix_load_index_summary",
            description="Get load index averages by time period and machine",
            inputSchema={
                "type": "object",
                "properties": {
                    "machine_id": {
                        "type": "string",
                        "description": "Machine ID (GUID, e.g. '31a02fb0-b673-4520-b94d-017fa2acd3b8')",
                    },
                    "machine_name": {
                        "type": "string",
                        "description": "Machine name (alternative to machine_id)",
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
            name="citrix_process_utilization",
            description="Get per-process CPU/memory utilization on a machine",
            inputSchema={
                "type": "object",
                "properties": {
                    "machine_id": {
                        "type": "string",
                        "description": "Machine ID (GUID, e.g. '31a02fb0-b673-4520-b94d-017fa2acd3b8')",
                    },
                    "machine_name": {
                        "type": "string",
                        "description": "Machine name (alternative to machine_id)",
                    },
                    "granularity": {
                        "type": "string",
                        "description": "Aggregation level",
                        "enum": ["raw", "minute", "hour", "day"],
                        "default": "raw",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 1)",
                        "default": 1,
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
            skip=arguments.get("skip"),
            expand=arguments.get("expand"),
            count=arguments.get("count", False),
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

    elif name == "citrix_load_index_summary":
        return client.get_load_index_summary(
            machine_id=arguments.get("machine_id"),
            machine_name=arguments.get("machine_name"),
            days=arguments.get("days", 7),
        )

    elif name == "citrix_process_utilization":
        return client.get_process_utilization(
            machine_id=arguments.get("machine_id"),
            machine_name=arguments.get("machine_name"),
            granularity=arguments.get("granularity", "raw"),
            days=arguments.get("days", 1),
            filter=arguments.get("filter"),
        )

    else:
        raise ValueError(f"Unknown tool: {name}")
