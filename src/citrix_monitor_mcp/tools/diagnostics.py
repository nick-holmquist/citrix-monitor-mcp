"""Probe and internal task-log tools for Citrix Monitor MCP."""

from typing import Any

from mcp.types import Tool

from ..client import get_client


def get_tools() -> list[Tool]:
    """Return probe and task-log tools."""
    return [
        Tool(
            name="citrix_probe_rules",
            description="List configured application probes (synthetic availability checks)",
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
            name="citrix_probe_endpoints",
            description="List machines running the Citrix Probe Agent",
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
            name="citrix_probe_logs",
            description="List probe run logs per application",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Custom OData filter expression",
                    },
                    "top": {
                        "type": "integer",
                        "description": "Maximum records to return",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_probe_results",
            description="List probe run results, including failure stage",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Custom OData filter expression",
                    },
                    "top": {
                        "type": "integer",
                        "description": "Maximum records to return",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="citrix_task_logs",
            description="List internal Monitor Service task/job execution logs",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Custom OData filter expression",
                    },
                    "top": {
                        "type": "integer",
                        "description": "Maximum records to return",
                    },
                },
                "required": [],
            },
        ),
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Handle probe and task-log tool calls."""
    client = get_client()

    if name == "citrix_probe_rules":
        return client.list_probe_rules(filter=arguments.get("filter"))

    elif name == "citrix_probe_endpoints":
        return client.list_probe_endpoints(filter=arguments.get("filter"))

    elif name == "citrix_probe_logs":
        return client.query(
            "ProbeLogs", filter=arguments.get("filter"), top=arguments.get("top")
        )

    elif name == "citrix_probe_results":
        return client.list_probe_results(
            filter=arguments.get("filter"), top=arguments.get("top")
        )

    elif name == "citrix_task_logs":
        return client.list_task_logs(
            filter=arguments.get("filter"), top=arguments.get("top")
        )

    else:
        raise ValueError(f"Unknown tool: {name}")
