# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed — live-server smoke test (2026-07-08)

A full smoke test of all 34 tools against a real Citrix Cloud Monitor Service (first live
credentials configured) found 3 hard failures and 3 tools that silently returned `null` for
valid IDs. All confirmed fixed by a second live smoke-test pass:

- **`Entity(key)` URL path-key-segment lookups 404 against this Monitor Service endpoint.**
  `client.query_single()` (used by `citrix_machine_status`, `citrix_session_details`,
  `citrix_user_details`) built URLs like `Machines(<guid>)` and treated the resulting 404 as "not
  found," so every keyed lookup silently returned `null` even for valid IDs. Rewrote
  `query_single()` to look records up via `$filter` (e.g. `Id eq <guid>`) instead, with a
  `key_field` parameter (`"Id"` by default, `"SessionKey"` for Sessions).
- **`/$count` path segment also 404s.** `client.get_count()` (used by `citrix_entity_count`,
  `citrix_session_count`) hit `Entity/$count` directly; switched to `$count=true&$top=0` on the
  base entity query, which returns the total via `@odata.count` without transferring records.
- **`SessionMetrics` has no `SessionKey` field.** `get_session_metrics()`/`citrix_session_metrics`
  filtered on `SessionKey`, but the entity's actual property is `SessionId` — every call 400'd.
  Fixed to filter on `SessionId`.

### Added

Expanded Monitor OData entity coverage to close gaps found against the full Citrix Monitor Service
schema:

- `citrix_catalog_list` — machine catalogs
- `citrix_connection_failure_categories` — failure category lookups
- `citrix_app_error_logs` — `ApplicationErrors` (distinct from the existing `citrix_app_errors`/`ApplicationFaults`)
- `citrix_app_activity_summary` — application usage rollups
- `citrix_session_metrics`, `citrix_session_activity_summary` — per-session metrics and activity rollups
- `citrix_load_index_summary` — load index rollups by period
- `citrix_process_utilization` — per-process CPU/memory utilization (raw/minute/hour/day granularity)
- `citrix_probe_rules`, `citrix_probe_endpoints`, `citrix_probe_logs`, `citrix_probe_results` — synthetic
  application-probe monitoring (new `tools/diagnostics.py` module)
- `citrix_task_logs` — internal Monitor Service task/job execution logs

### Fixed

- `client.query()` accepted a `count` parameter and sent `$count=true` to the API, but silently
  discarded the returned `@odata.count` total — only the record list was ever returned. Now returns
  `{"count": total, "value": [...]}` when `count=True`, and `citrix_query_raw` exposes `count`/`skip`
  (previously `skip` wasn't wired through despite the client supporting it).
- Removed redundant per-method `from datetime import datetime, timedelta` re-imports in `client.py`
  (already imported at module scope).
- Clarified the `citrix_app_errors` tool description to distinguish it from the new
  `citrix_app_error_logs` (they map to the distinct `ApplicationFaults` and `ApplicationErrors`
  entities, respectively).

### Fixed — API-correctness audit (external review against Citrix's official OData docs)

An independent audit against Citrix's Monitor Service OData documentation (enums, entity
schemas, `Monitor.Model`) turned up several bugs that would have caused real request failures
or silent wrong results against a live server:

- **Enum filters sent as strings, but the API requires integers.** `CurrentRegistrationState`/
  `CurrentPowerState` are OData enums, which Citrix does not support comparing against string
  literals — `list_machines()`/`citrix_machine_list` now translates the tool's string enum values
  (`"Registered"`, `"On"`, etc.) to the documented integer codes before sending the filter.
  `power_state`'s enum list was also expanded to all 12 documented `PowerStateCode` values (was
  previously missing 8 of them).
- **`Machines.Id` and `Applications.Id` are GUIDs, not integers.** `machine_id`/`app_id`
  parameters were typed `integer` in every tool schema and client method; changed to `string`
  throughout (`citrix_machine_status`, `citrix_machine_metrics`, `citrix_machine_failures`,
  `citrix_load_index`, `citrix_load_index_summary`, `citrix_process_utilization`,
  `citrix_app_instances`).
- **`SessionKey` is `Edm.Guid`; quoted-string key/filter syntax is invalid OData v4.** Removed
  the incorrect single-quotes around `SessionKey` in `get_session`, `get_logon_metrics`,
  `get_session_metrics`, and `list_connections` — GUID literals must be unquoted
  (`SessionKey eq 4569fdfd-...`, not `SessionKey eq '4569fdfd-...'`).
- **Wrong entity name: `SessionMetric` → `SessionMetrics`** (plural) in `get_session_metrics` —
  was 404ing on every call.
- **Removed `citrix_app_instance_summary`.** `ApplicationInstanceSummary` is not an exposed
  entity set in the current Monitor Service schema; the tool would always fail. Use
  `citrix_app_activity_summary` for application usage rollups instead.
- **`ConnectionFailureLogs` has no `DesktopGroup` navigation property.** The invalid
  `$expand=DesktopGroup` was causing `citrix_connection_failures` to fail entirely (not just lose
  the delivery-group filter). Removed the `delivery_group` parameter and the expand; documented
  the gap in Known Limitations.
- **`ApplicationFaults`/`ApplicationErrors` have no `Application` navigation property**, and use
  `FaultReportedDate`/`ErrorReportedDate` respectively, not `CreatedDate`. The invalid
  `$expand=Application` was causing `citrix_app_errors`/`citrix_app_error_logs` to fail entirely.
  `app_name` now filters via `contains(ProcessName, ...)` against the real schema instead.
- **429 retry now honors `Retry-After`** when the server sends one, falling back to the existing
  fixed backoff otherwise.
- README: corrected the documented page size (Citrix's current docs say 1000 records/page, not
  100) and softened the unsourced "1 concurrent query / 30s timeout" claim.

### Documentation

- README: corrected MCP configuration guidance — credentials belong only in `.env`, not inline in
  `~/.claude.json`'s `mcpServers` block.
- README: added an OData filter-syntax cheatsheet (date literals, navigation properties, `contains`,
  null checks) to make `filter` parameters easier for an agent to construct correctly on the first try.
- README: documented how to connect multiple Citrix environments (separate installed copies +
  separate MCP server registrations, each with its own `.env`) since the server has no built-in
  multi-site/`site` parameter concept.
- README: added a not-affiliated-with-Citrix / use-at-your-own-risk disclaimer up top — this is an
  independent, unofficial project with no Citrix support agreement or warranty behind it.
- README: added a Security Notes section (authentication model, trust boundaries, known
  non-goals) and a Known Limitations bullet calling out unbounded list-tool result sizes.
