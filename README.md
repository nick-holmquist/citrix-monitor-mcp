# Citrix Monitor MCP

An MCP (Model Context Protocol) server for querying Citrix Monitor Service OData API. Supports both Citrix Cloud (DaaS) and on-premises CVAD deployments.

> **⚠️ Not affiliated with or supported by Citrix.** This is an independent, unofficial project.
> It is not a Citrix product, is not endorsed by Cloud Software Group/Citrix, and is not covered
> by any Citrix support agreement, SLA, or warranty. It talks to the Monitor Service OData API
> using publicly documented endpoints, but Citrix did not review, certify, or sign off on this
> code. **Use at your own risk:**
> - Query Citrix's official docs (linked in this README) yourself before trusting field/entity
>   names for your specific CVAD/DaaS version — schemas can differ across versions and this
>   project has not been validated against every one.
> - Read-heavy or malformed queries against a production Monitor Service can affect Director and
>   other consumers of the same API (Citrix documents a 1-concurrent-query-per-customer limit) —
>   test against a non-production site first.
> - Credentials configured here (client secret, on-prem admin password) grant whatever the
>   underlying Citrix account can see; scope that account's permissions appropriately.
> - No warranty of any kind, express or implied. You are responsible for validating results
>   before acting on them (capacity decisions, alerting, etc.).
>
> Found a bug or a Citrix API mismatch? Please open an issue/PR — this project does not have a
> vendor support line to fall back on.

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

**Where credentials live:** this server reads all configuration from a `.env` file — never
from the MCP server registration. `client.py` loads `.env` first from the current working
directory, then falls back to `.env` next to the installed package (needed because Claude
Code launches the server as a subprocess, so the working directory isn't guaranteed to be
this repo). Set up `.env` as described in [Configuration](#configuration) above and keep it
out of version control (it's already gitignored).

Add to your Claude Code MCP configuration — no secrets belong in this file, since
`~/.claude.json` is not treated as a secret store and may be synced/backed up:

```json
{
  "mcpServers": {
    "citrix-monitor": {
      "command": "citrix-monitor-mcp"
    }
  }
}
```

If you need to run multiple Citrix sites from the same machine, use a separate installed copy
of this package per site, each with its own `.env` next to its package installation, rather than
passing per-site secrets inline through `env` in this JSON. See
[Connecting to Multiple Citrix Environments](#connecting-to-multiple-citrix-environments) below.

## Connecting to Multiple Citrix Environments

This server has no built-in concept of "sites" or a `site` parameter — each running server
process talks to exactly one Citrix environment, determined entirely by its `.env`. To monitor
more than one environment (e.g. prod + a lab/DR site, or Cloud + an on-prem CVAD farm), run a
**separate installed copy of the package per environment** and register each as its own MCP
server. Claude Code namespaces tool calls by server, so `citrix-monitor-prod` and
`citrix-monitor-lab` can both be connected at once with no risk of a query hitting the wrong
environment and no code changes required.

Because this repo is normally installed with `pip install -e .` (an editable install), the
package's `.env` fallback (`client.py`) resolves back to this repo's own root directory — so
each separate checkout/install of the repo carries its own independent `.env`.

**Steps (repeat per environment):**

```bash
# 1. Clone/copy this repo to a per-environment directory
git clone <this-repo> E:\dev\citrix-monitor-mcp-prod
cd E:\dev\citrix-monitor-mcp-prod

# 2. Create an isolated virtual environment and install into it
python -m venv .venv
.venv\Scripts\pip install -e .

# 3. Configure this copy's own .env for that environment
copy .env.example .env
# edit .env with this environment's CITRIX_* credentials
```

Then register each copy under a distinct name, pointing `command` at that venv's installed
executable:

```json
{
  "mcpServers": {
    "citrix-monitor-prod": {
      "command": "E:\\dev\\citrix-monitor-mcp-prod\\.venv\\Scripts\\citrix-monitor-mcp.exe"
    },
    "citrix-monitor-lab": {
      "command": "E:\\dev\\citrix-monitor-mcp-lab\\.venv\\Scripts\\citrix-monitor-mcp.exe"
    }
  }
}
```

Each server only ever reads its own `.env`, so credentials for different environments are never
loaded into the same process — and an agent working across both sees clearly distinct tool
namespaces (e.g. `citrix-monitor-prod`'s `citrix_machine_list` vs. `citrix-monitor-lab`'s) instead
of one ambiguous tool that silently switches environments.

*Why not a `site` parameter on every tool instead?* That would require a shared credential
registry inside one process and a `site` argument threaded through all ~37 tools — a real
architecture change whose only benefit is comparing two environments within a single
conversation without switching server context. For most use cases the separate-registration
approach above gets full multi-environment support today with zero code changes.

## Available Tools

### Machines
| Tool | Description |
|------|-------------|
| `citrix_machine_list` | List all machines with optional filters |
| `citrix_machine_status` | Get specific machine details |
| `citrix_machine_metrics` | CPU/memory usage metrics |
| `citrix_machine_failures` | Machine failure logs |
| `citrix_catalog_list` | List machine catalogs |

### Sessions
| Tool | Description |
|------|-------------|
| `citrix_session_list` | List sessions (active/all) |
| `citrix_session_details` | Get session by key |
| `citrix_session_logon_metrics` | Logon duration breakdown |
| `citrix_session_count` | Count sessions |
| `citrix_session_metrics` | Per-session ICA/bandwidth metrics |
| `citrix_session_activity_summary` | Session activity rollups by period |

### Connections
| Tool | Description |
|------|-------------|
| `citrix_connection_list` | List connections |
| `citrix_connection_failures` | Connection failure logs (no delivery-group filter — see Known Limitations) |
| `citrix_failure_summary` | Failure counts by period |
| `citrix_connection_failure_categories` | Connection failure category lookups |

### Applications
| Tool | Description |
|------|-------------|
| `citrix_app_list` | List published applications |
| `citrix_app_instances` | Running app instances |
| `citrix_app_errors` | Application faults (ApplicationFaults); `app_name` matches ProcessName |
| `citrix_app_error_logs` | Application error log entries (ApplicationErrors); `app_name` matches ProcessName |
| `citrix_app_activity_summary` | Application usage rollups by period |

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
| `citrix_load_index_summary` | Load index rollups by period |
| `citrix_process_utilization` | Per-process CPU/memory on a machine (raw/minute/hour/day) |
| `citrix_entity_count` | Count entities |
| `citrix_aggregate` | OData aggregations |

### Diagnostics
| Tool | Description |
|------|-------------|
| `citrix_probe_rules` | List configured application probes |
| `citrix_probe_endpoints` | List machines running the Probe Agent |
| `citrix_probe_logs` | Probe run logs per application |
| `citrix_probe_results` | Probe run results, including failure stage |
| `citrix_task_logs` | Internal Monitor Service task/job logs |

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

### Total count without downloading all records
```
citrix_query_raw(entity="Sessions", filter="EndDate eq null", top=1, count=true)
# -> {"count": 842, "value": [ ...one sample record... ]}
```

## OData Filter Syntax Cheatsheet

For `citrix_query_raw`, `citrix_aggregate`, and any tool's `filter` parameter:

| Pattern | Example |
|---------|---------|
| Equality | `Name eq 'VDA01'` |
| Comparison | `LogOnDuration gt 60000`, `CurrentLoadIndex ge 8000` |
| Boolean combine | `EndDate eq null and Machine/Name eq 'VDA01'` |
| Date/time literal | `CreatedDate ge 2024-01-01T00:00:00Z` (ISO 8601, UTC, no quotes) |
| Null check | `EndDate eq null` (active session/instance) |
| Navigation property | `Machine/Name eq 'VDA01'`, `Application/Name eq 'Notepad'`, `User/UserName eq 'DOMAIN\\jsmith'` |
| String contains | `contains(Name, 'VDA')` |

Entity/field names are case-sensitive and vary by entity — if a filter 400s, use
`citrix_query_raw(entity="<name>")` with no filter first to see the actual field names on
your Site's schema version.

## API Rate Limits

- **Page size**: current Citrix docs state OData v4 endpoints return up to **1000 records per
  page**, with `@odata.nextLink` to the next page — pagination is handled automatically by this
  client regardless of the actual page size.
- **Concurrency**: Citrix enforces a per-customer concurrency limit and returns `429` when
  exceeded, but the exact limit and per-query timeout are not published in current docs (older
  community guidance cited "1 concurrent query" / "30 second timeout" — treat that as indicative
  of the order of magnitude, not a guaranteed contract).

The client automatically retries on `429` responses, honoring the `Retry-After` header when the
server sends one and falling back to a fixed exponential backoff otherwise.

## Known Limitations

- The Monitor OData schema includes entities whose exact field names are not fully published by Citrix
  (notably `ProbeRules`, `ProbeEndpoints`, `ProbeLogs`, `ProbeResults`, `TaskLogs`). Tools for these
  entities expose only pass-through `filter`/`top` parameters rather than named convenience filters —
  use `citrix_query_raw` with `$metadata` inspection if you need to discover exact field names for your
  Site's schema version.
- Summary/rollup entities (e.g. `SessionActivitySummaries`, `ApplicationActivitySummaries`,
  `LoadIndexSummaries`) are queried using a `SummaryDate` field by convention (matching
  `FailureLogSummaries`, which is confirmed). If a given deployment's schema differs, pass a custom
  `filter` to override.
- Most list-style tools (`citrix_machine_list`, `citrix_session_list`, `citrix_connection_list`,
  `citrix_app_list`, `citrix_app_instances`, `citrix_user_list`) have no built-in result cap — on a
  large Site they can pull an unbounded number of records against a Monitor Service that enforces
  per-customer concurrency limits. Pass a custom `filter` to narrow scope on large environments, or
  use `citrix_query_raw` with an explicit `top`.
- `citrix_connection_failures` cannot filter by delivery group — `ConnectionFailureLogs` has no
  `DesktopGroup` navigation property (confirmed against Citrix's documented field list). Pass a
  custom `filter` against `Machine`/`User`/`Session` if you need to scope by delivery group through
  one of those relationships instead.
- `citrix_app_errors`/`citrix_app_error_logs` (`ApplicationFaults`/`ApplicationErrors`) have no
  `Application` navigation property — their `app_name` parameter matches against `ProcessName`
  (e.g. `notepad.exe`), not a published-application display name.
- Machine and Application IDs (`machine_id`, `app_id`) are GUIDs (`Edm.Guid`), not integers — pass
  them as strings, e.g. `"31a02fb0-b673-4520-b94d-017fa2acd3b8"`.

## Security Notes

### Authentication model

- **Citrix Cloud (DaaS)**: OAuth 2.0 client-credentials grant against the region's
  `cctrustoauth2` endpoint. The resulting bearer token is cached in memory only (never
  written to disk or logged) and refreshed automatically 5 minutes before expiry. Requests to
  the Monitor OData API carry it as `Authorization: CWSAuth bearer=<token>` plus a
  `Citrix-CustomerId` header.
- **On-premises (CVAD)**: NTLM authentication using a domain service/admin account
  (`CITRIX_DOMAIN`\\`CITRIX_USERNAME`/`CITRIX_PASSWORD`) sent on every request via
  `requests_ntlm`.
- In both modes, credentials are read exclusively from `.env` at process start (see
  [Configuration](#configuration)) — never accepted as tool arguments, never echoed in tool
  output, and never included in error messages returned to the calling agent.

### Trust boundaries

- **The Citrix Monitor Service is treated as trusted-but-remote**: TLS certificate verification
  is on by default (`CITRIX_VERIFY_SSL=true`); disabling it (on-prem self-signed certs) is an
  explicit opt-in and weakens that boundary — only do this on a network you control.
- **Any agent connected to this MCP server is fully trusted with read access to the entire
  Monitor Service dataset the configured account can see.** There is no per-tool authorization
  layer in this server — `citrix_query_raw` in particular allows querying *any* entity with *any*
  filter, so tool-level restrictions are not a meaningful security boundary here. The real
  boundary is the permissions granted to the underlying Citrix Cloud API client / on-prem
  service account; scope that account down (read-only Monitor role, not a full administrator) if
  the agent should not be able to see everything the account can.
- **`.env` is the sole secret boundary.** Anyone with filesystem read access to it (or to the
  running process's environment) has full API credentials. Standard OS file permissions are the
  only protection — this project does not integrate with a secrets manager/vault.

### Known non-goals

- **No write/mutation support.** The Monitor Service OData API is itself read-only for the
  entities this server queries, and no tool here performs a create/update/delete — there is
  nothing to authorize beyond read access.
- **No RBAC or per-tool permissioning beyond the underlying Citrix account.** If that account can
  see a delivery group, session, or user, so can any agent using this server.
- **No secret rotation, vaulting, or audit logging of credential use.**
- **No multi-tenant isolation within a single process** — see
  [Connecting to Multiple Citrix Environments](#connecting-to-multiple-citrix-environments) for
  why that's handled via separate server registrations instead.
- **No protection against expensive/abusive query patterns** beyond Citrix's own rate limiting —
  this server retries on 429 but does not itself throttle, cap result sizes, or estimate query
  cost before sending a request (see [Known Limitations](#known-limitations) re: unbounded list
  queries).

## License

MIT
