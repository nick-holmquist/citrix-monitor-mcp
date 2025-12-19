# Citrix Monitor MCP

An MCP (Model Context Protocol) server for querying Citrix Monitor Service OData API. Supports both Citrix Cloud (DaaS) and on-premises CVAD deployments.

## Features

- **Dual deployment support**: Works with Citrix Cloud and on-premises CVAD
- **Comprehensive monitoring**: Machines, sessions, connections, applications, users
- **Analytics**: Custom OData queries, aggregations, failure summaries
- **Rate limit handling**: Automatic retry with backoff for 429 responses
- **Pagination**: Automatic handling of paginated responses

## Installation

```bash
pip install -e .
```

Or with uv:

```bash
uv pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and configure:

### Citrix Cloud (DaaS)

```env
CITRIX_DEPLOYMENT=cloud
CITRIX_CUSTOMER_ID=your-customer-id
CITRIX_CLIENT_ID=your-client-id
CITRIX_CLIENT_SECRET=your-client-secret
CITRIX_REGION=us  # us, eu, ap-s, jp
```

### On-Premises (CVAD)

```env
CITRIX_DEPLOYMENT=onprem
CITRIX_DDC_HOST=https://ddc.example.com
CITRIX_DOMAIN=YOURDOMAIN
CITRIX_USERNAME=admin
CITRIX_PASSWORD=your-password
```

## Usage with Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "citrix-monitor": {
      "command": "citrix-monitor-mcp",
      "env": {
        "CITRIX_DEPLOYMENT": "cloud",
        "CITRIX_CUSTOMER_ID": "your-customer-id",
        "CITRIX_CLIENT_ID": "your-client-id",
        "CITRIX_CLIENT_SECRET": "your-client-secret",
        "CITRIX_REGION": "us"
      }
    }
  }
}
```

## Available Tools

### Machines
| Tool | Description |
|------|-------------|
| `citrix_machine_list` | List all machines with optional filters |
| `citrix_machine_status` | Get specific machine details |
| `citrix_machine_metrics` | CPU/memory usage metrics |
| `citrix_machine_failures` | Machine failure logs |

### Sessions
| Tool | Description |
|------|-------------|
| `citrix_session_list` | List sessions (active/all) |
| `citrix_session_details` | Get session by key |
| `citrix_session_logon_metrics` | Logon duration breakdown |
| `citrix_session_count` | Count sessions |

### Connections
| Tool | Description |
|------|-------------|
| `citrix_connection_list` | List connections |
| `citrix_connection_failures` | Connection failure logs |
| `citrix_failure_summary` | Failure counts by period |

### Applications
| Tool | Description |
|------|-------------|
| `citrix_app_list` | List published applications |
| `citrix_app_instances` | Running app instances |
| `citrix_app_errors` | Application errors/faults |

### Users
| Tool | Description |
|------|-------------|
| `citrix_user_list` | List users |
| `citrix_user_details` | Get user details |
| `citrix_user_sessions` | User session history |

### Analytics
| Tool | Description |
|------|-------------|
| `citrix_query_raw` | Execute custom OData query |
| `citrix_delivery_groups` | List delivery groups |
| `citrix_hypervisors` | List hypervisors |
| `citrix_load_index` | Machine load data |
| `citrix_entity_count` | Count entities |
| `citrix_aggregate` | OData aggregations |

## Example Queries

### List all registered machines
```
citrix_machine_list(registration_state="Registered")
```

### Get active sessions for a user
```
citrix_session_list(user_name="DOMAIN\\jsmith", active_only=true)
```

### Find connection failures in last 24 hours
```
citrix_connection_failures(days=1)
```

### Custom OData query
```
citrix_query_raw(
  entity="Sessions",
  filter="LogOnDuration gt 60000",
  select=["SessionKey", "LogOnDuration", "StartDate"],
  orderby="LogOnDuration desc",
  top=10
)
```

## API Rate Limits

The Citrix Monitor Service has the following limits:
- **1 concurrent query** per customer
- **30 second timeout** per query
- **100 records per page** (pagination handled automatically)

The client automatically retries on 429 (rate limit) responses with exponential backoff.

## License

MIT
