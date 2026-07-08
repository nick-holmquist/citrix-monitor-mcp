"""Citrix Monitor Service OData API client."""

import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests_ntlm import HttpNtlmAuth

logger = logging.getLogger(__name__)

# Try loading .env from multiple locations
# 1. Current working directory (default)
# 2. Package installation directory (for MCP usage)
load_dotenv()
_pkg_env = Path(__file__).parent.parent.parent / ".env"
if _pkg_env.exists():
    load_dotenv(_pkg_env)

_GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _odata_quote(value: str) -> str:
    """Escape a string for safe embedding in a single-quoted OData string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def _odata_key(value: str | int) -> str:
    """Validate and format a GUID or integer key for unquoted OData literal use.

    Monitor Service GUID/int keys are interpolated unquoted into $filter
    expressions (per OData v4 syntax); reject anything that isn't actually
    a GUID or integer so arbitrary filter clauses can't be injected here.
    """
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if _GUID_RE.match(text) or text.lstrip("-").isdigit():
        return text
    raise ValueError(f"Invalid entity key '{value}': expected a GUID or integer")


class CitrixMonitorClient:
    """Client for Citrix Monitor Service OData API.

    Supports both Citrix Cloud (DaaS) and on-premises (CVAD) deployments.
    """

    # Regional API endpoints for Citrix Cloud
    CLOUD_ENDPOINTS = {
        "us": "https://api-us.cloud.com",
        "eu": "https://api-eu.cloud.com",
        "ap-s": "https://api-ap-s.cloud.com",
        "jp": "https://api.citrixcloud.jp",
    }

    def __init__(self):
        self._session: requests.Session | None = None
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    @property
    def deployment_type(self) -> str:
        """Get deployment type (cloud or onprem)."""
        return os.getenv("CITRIX_DEPLOYMENT", "cloud").lower()

    @property
    def verify_ssl(self) -> bool:
        """Check if SSL verification is enabled."""
        return os.getenv("CITRIX_VERIFY_SSL", "true").lower() == "true"

    @property
    def base_url(self) -> str:
        """Get the base OData URL for the configured deployment."""
        if self.deployment_type == "cloud":
            region = os.getenv("CITRIX_REGION", "us").lower()
            endpoint = self.CLOUD_ENDPOINTS.get(region, self.CLOUD_ENDPOINTS["us"])
            return f"{endpoint}/monitorodata"
        else:
            host = os.getenv("CITRIX_DDC_HOST", "").rstrip("/")
            return f"{host}/Citrix/Monitor/OData/v4/Data"

    def _get_cloud_token(self) -> str:
        """Get OAuth bearer token for Citrix Cloud."""
        # Check if we have a valid cached token
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token

        customer_id = os.getenv("CITRIX_CUSTOMER_ID")
        client_id = os.getenv("CITRIX_CLIENT_ID")
        client_secret = os.getenv("CITRIX_CLIENT_SECRET")
        region = os.getenv("CITRIX_REGION", "us").lower()

        if not all([customer_id, client_id, client_secret]):
            raise ValueError(
                "Missing cloud credentials. Set CITRIX_CUSTOMER_ID, "
                "CITRIX_CLIENT_ID, and CITRIX_CLIENT_SECRET"
            )

        # Get the auth endpoint for the region
        endpoint = self.CLOUD_ENDPOINTS.get(region, self.CLOUD_ENDPOINTS["us"])
        token_url = f"{endpoint}/cctrustoauth2/{customer_id}/tokens/clients"

        try:
            response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                verify=self.verify_ssl,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            # Don't let the token endpoint URL (which embeds CITRIX_CUSTOMER_ID)
            # or raw response body leak into the error surfaced to the MCP client.
            logger.warning("Citrix Cloud token request failed: %s", e)
            raise RuntimeError(
                "Failed to obtain Citrix Cloud auth token. Check CITRIX_CUSTOMER_ID, "
                "CITRIX_CLIENT_ID, CITRIX_CLIENT_SECRET, and network connectivity."
            ) from None

        token_data = response.json()
        self._token = token_data["access_token"]
        # Token typically expires in 1 hour, refresh 5 minutes early
        expires_in = int(token_data.get("expires_in", 3600))
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)

        return self._token

    @property
    def session(self) -> requests.Session:
        """Get configured requests session with appropriate auth."""
        if self._session is None:
            if not self.verify_ssl:
                logger.warning(
                    "CITRIX_VERIFY_SSL is disabled — TLS certificate validation is "
                    "off for all Citrix API requests."
                )
            self._session = requests.Session()
            self._session.verify = self.verify_ssl

            if self.deployment_type == "cloud":
                # Cloud uses bearer token auth
                token = self._get_cloud_token()
                customer_id = os.getenv("CITRIX_CUSTOMER_ID")
                self._session.headers.update({
                    "Authorization": f"CWSAuth bearer={token}",
                    "Citrix-CustomerId": customer_id,
                    "Accept": "application/json",
                })
            else:
                # On-prem uses NTLM auth
                domain = os.getenv("CITRIX_DOMAIN", "")
                username = os.getenv("CITRIX_USERNAME", "")
                password = os.getenv("CITRIX_PASSWORD", "")

                if not all([username, password]):
                    raise ValueError(
                        "Missing on-prem credentials. Set CITRIX_USERNAME and CITRIX_PASSWORD"
                    )

                self._session.auth = HttpNtlmAuth(f"{domain}\\{username}", password)
                self._session.headers.update({"Accept": "application/json"})

        return self._session

    def _refresh_cloud_session(self):
        """Refresh cloud token if needed."""
        if self.deployment_type == "cloud":
            token = self._get_cloud_token()
            self.session.headers["Authorization"] = f"CWSAuth bearer={token}"

    def _request_with_retry(
        self, method: str, url: str, max_retries: int = 3, **kwargs
    ) -> requests.Response:
        """Execute request with retry logic for rate limiting."""
        for attempt in range(max_retries):
            # Refresh token if needed for cloud deployments
            if self.deployment_type == "cloud":
                self._refresh_cloud_session()

            response = self.session.request(method, url, **kwargs)

            if response.status_code == 429:
                # Rate limited - honor Retry-After if the server sent one,
                # otherwise fall back to a fixed exponential backoff.
                retry_after = response.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = 5 * (attempt + 1)
                else:
                    wait_time = 5 * (attempt + 1)
                time.sleep(wait_time)
                continue

            return response

        raise Exception(f"Rate limited after {max_retries} retries")

    def query(
        self,
        entity: str,
        filter: str | None = None,
        select: list[str] | None = None,
        orderby: str | None = None,
        top: int | None = None,
        skip: int | None = None,
        expand: list[str] | None = None,
        count: bool = False,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Execute OData query with automatic pagination.

        Args:
            entity: Entity name (e.g., "Machines", "Sessions")
            filter: OData $filter expression
            select: List of fields to select
            orderby: OData $orderby expression
            top: Maximum records to return (per page if paginating)
            skip: Number of records to skip
            expand: List of related entities to expand
            count: If True, return {"count": total, "value": records} instead
                of a bare list, where "count" is the server-reported total
                matching the filter (independent of pagination/top).

        Returns:
            List of entity records, or a dict with "count" and "value" when
            count=True.
        """
        params = {}
        if filter:
            params["$filter"] = filter
        if select:
            params["$select"] = ",".join(select)
        if orderby:
            params["$orderby"] = orderby
        if top:
            params["$top"] = top
        if skip:
            params["$skip"] = skip
        if expand:
            params["$expand"] = ",".join(expand)
        if count:
            params["$count"] = "true"

        results = []
        total_count = None
        url = f"{self.base_url}/{entity}"

        while url:
            response = self._request_with_retry("GET", url, params=params)
            response.raise_for_status()
            data = response.json()

            if total_count is None and "@odata.count" in data:
                total_count = data["@odata.count"]

            results.extend(data.get("value", []))

            # Follow pagination link if present
            url = data.get("@odata.nextLink")
            params = None  # Only use params on first request

        if count:
            return {"count": total_count, "value": results}
        return results

    def query_single(
        self,
        entity: str,
        key: str | int,
        expand: list[str] | None = None,
        key_field: str = "Id",
    ) -> dict[str, Any] | None:
        """Query a single entity by key field.

        The Monitor Service OData endpoint does not support the standard
        Entity(key) URL path-key-segment convention (it 404s even for valid
        keys), so this looks the record up via $filter instead.

        Args:
            entity: Entity name
            key: Entity key value (GUID or int; passed unquoted into the filter)
            expand: List of related entities to expand
            key_field: Name of the key property to filter on (default "Id")

        Returns:
            Entity record or None if not found
        """
        results = self.query(
            entity, filter=f"{key_field} eq {_odata_key(key)}", expand=expand, top=1
        )
        return results[0] if results else None

    def aggregate(self, entity: str, apply: str) -> dict[str, Any]:
        """Execute OData aggregation query.

        Args:
            entity: Entity name
            apply: OData $apply expression (e.g., "aggregate(SessionCount with sum as Total)")

        Returns:
            Aggregation result
        """
        url = f"{self.base_url}/{entity}"
        params = {"$apply": apply}

        response = self._request_with_retry("GET", url, params=params)
        response.raise_for_status()
        return response.json()

    def get_count(self, entity: str, filter: str | None = None) -> int:
        """Get count of entities matching filter.

        The Monitor Service OData endpoint does not support the /$count path
        segment (it 404s), so this uses $count=true with $top=0 to get just
        the total without transferring any records.

        Args:
            entity: Entity name
            filter: Optional OData $filter expression

        Returns:
            Count of matching entities
        """
        url = f"{self.base_url}/{entity}"
        params = {"$count": "true", "$top": 0}
        if filter:
            params["$filter"] = filter

        response = self._request_with_retry("GET", url, params=params)
        response.raise_for_status()
        return int(response.json().get("@odata.count", 0))

    # =========================================================================
    # Machine methods
    # =========================================================================

    # OData enums are transmitted as integers, not strings (Monitor Service does
    # not support Edm.String comparisons against enum-typed fields). Mappings
    # per https://developer-docs.citrix.com/en-us/monitor-service-odata-api/monitor-service-enums.html
    REGISTRATION_STATES = {
        "Unknown": 0,
        "Registered": 1,
        "Unregistered": 2,
    }
    POWER_STATES = {
        "Unknown": 0,
        "Unavailable": 1,
        "Off": 2,
        "On": 3,
        "Suspended": 4,
        "TurningOn": 5,
        "TurningOff": 6,
        "Suspending": 7,
        "Resuming": 8,
        "Unmanaged": 9,
        "NotSupported": 10,
        "VirtualMachineNotFound": 11,
    }

    def list_machines(
        self,
        filter: str | None = None,
        registration_state: str | None = None,
        power_state: str | None = None,
        in_maintenance: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List machines with optional filters."""
        filters = []
        if filter:
            filters.append(filter)
        if registration_state:
            state_value = self.REGISTRATION_STATES.get(registration_state)
            if state_value is None:
                raise ValueError(
                    f"Unknown registration_state '{registration_state}'. "
                    f"Valid values: {sorted(self.REGISTRATION_STATES)}"
                )
            filters.append(f"CurrentRegistrationState eq {state_value}")
        if power_state:
            state_value = self.POWER_STATES.get(power_state)
            if state_value is None:
                raise ValueError(
                    f"Unknown power_state '{power_state}'. "
                    f"Valid values: {sorted(self.POWER_STATES)}"
                )
            filters.append(f"CurrentPowerState eq {state_value}")
        if in_maintenance is not None:
            filters.append(f"IsInMaintenanceMode eq {str(in_maintenance).lower()}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query("Machines", filter=combined_filter)

    def get_machine(self, machine_id: str) -> dict[str, Any] | None:
        """Get machine by ID (Machines.Id is an Edm.Guid, e.g. '31a02fb0-b673-4520-b94d-017fa2acd3b8')."""
        return self.query_single("Machines", machine_id)

    def get_machine_by_name(self, name: str) -> dict[str, Any] | None:
        """Get machine by name."""
        machines = self.query("Machines", filter=f"Name eq {_odata_quote(name)}", top=1)
        return machines[0] if machines else None

    def get_machine_metrics(
        self, machine_id: str | None = None, name: str | None = None
    ) -> list[dict[str, Any]]:
        """Get machine resource utilization metrics."""
        if name:
            machine = self.get_machine_by_name(name)
            if machine:
                machine_id = machine.get("Id")

        if not machine_id:
            return []

        return self.query(
            "ResourceUtilization",
            filter=f"MachineId eq {_odata_key(machine_id)}",
            orderby="CreatedDate desc",
        )

    def get_machine_failures(
        self, machine_id: str | None = None, name: str | None = None
    ) -> list[dict[str, Any]]:
        """Get machine failure logs."""
        if name:
            machine = self.get_machine_by_name(name)
            if machine:
                machine_id = machine.get("Id")

        if not machine_id:
            return []

        return self.query(
            "MachineFailureLogs",
            filter=f"MachineId eq {_odata_key(machine_id)}",
            orderby="FailureStartDate desc",
        )

    def list_catalogs(self, filter: str | None = None) -> list[dict[str, Any]]:
        """List machine catalogs."""
        return self.query("Catalogs", filter=filter)

    # =========================================================================
    # Session methods
    # =========================================================================

    def list_sessions(
        self,
        filter: str | None = None,
        active_only: bool = False,
        user_name: str | None = None,
        machine_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """List sessions with optional filters."""
        filters = []
        if filter:
            filters.append(filter)
        if active_only:
            filters.append("EndDate eq null")
        if user_name:
            filters.append(f"User/UserName eq {_odata_quote(user_name)}")
        if machine_name:
            filters.append(f"Machine/Name eq {_odata_quote(machine_name)}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "Sessions",
            filter=combined_filter,
            expand=["User", "Machine"],
            orderby="StartDate desc",
        )

    def get_session(self, session_key: str) -> dict[str, Any] | None:
        """Get session by key (Sessions.SessionKey is an Edm.Guid; the key
        segment must be an unquoted GUID literal per OData v4, e.g.
        Sessions(4569fdfd-54c4-44c8-81a9-40688a2771d6))."""
        return self.query_single(
            "Sessions", session_key, expand=["User", "Machine"], key_field="SessionKey"
        )

    def get_logon_metrics(self, session_key: str) -> list[dict[str, Any]]:
        """Get logon duration breakdown for a session."""
        return self.query(
            "LogOnMetrics",
            filter=f"SessionKey eq {_odata_key(session_key)}",
        )

    def get_session_metrics(
        self, session_key: str | None = None, filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Get per-session ICA/bandwidth metrics.

        SessionMetrics has no SessionKey property — it keys sessions via
        SessionId (an Edm.Guid matching Sessions.SessionKey's value).
        """
        filters = []
        if filter:
            filters.append(filter)
        if session_key:
            filters.append(f"SessionId eq {_odata_key(session_key)}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query("SessionMetrics", filter=combined_filter)

    def get_session_activity_summary(
        self, days: int = 7, filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Get session count/logon activity rollups by time period."""
        filters = []
        if filter:
            filters.append(filter)

        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"SummaryDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "SessionActivitySummaries",
            filter=combined_filter,
            orderby="SummaryDate desc",
        )

    # =========================================================================
    # Connection methods
    # =========================================================================

    def list_connections(
        self,
        filter: str | None = None,
        session_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """List connections."""
        filters = []
        if filter:
            filters.append(filter)
        if session_key:
            filters.append(f"SessionKey eq {_odata_key(session_key)}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "Connections",
            filter=combined_filter,
            orderby="LogOnStartDate desc",
        )

    def get_connection_failures(
        self,
        filter: str | None = None,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get connection failure logs.

        Note: ConnectionFailureLogs has no DesktopGroup navigation property
        (fields are Id, SessionKey, FailureDate, UserId, MachineId,
        ConnectionFailureEnumValue, Created/ModifiedDate; documented $expand
        targets are Machine, User, Session only) — delivery-group filtering
        is not supported here. Pass a custom `filter` against Machine/User/
        Session if you need to scope by delivery group via one of those.
        """
        filters = []
        if filter:
            filters.append(filter)

        # Default to last N days
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"FailureDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "ConnectionFailureLogs",
            filter=combined_filter,
            orderby="FailureDate desc",
        )

    def list_connection_failure_categories(self) -> list[dict[str, Any]]:
        """List connection failure category lookup values."""
        return self.query("ConnectionFailureCategories")

    # =========================================================================
    # Application methods
    # =========================================================================

    def list_applications(self, filter: str | None = None) -> list[dict[str, Any]]:
        """List published applications."""
        return self.query("Applications", filter=filter)

    def list_app_instances(
        self,
        app_id: str | None = None,
        app_name: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List running application instances."""
        filters = []
        if app_id:
            filters.append(f"ApplicationId eq {_odata_key(app_id)}")
        if app_name:
            filters.append(f"Application/Name eq {_odata_quote(app_name)}")
        if active_only:
            filters.append("EndDate eq null")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "ApplicationInstances",
            filter=combined_filter,
            expand=["Application"],
            orderby="StartDate desc",
        )

    def get_app_errors(
        self, app_name: str | None = None, days: int = 7
    ) -> list[dict[str, Any]]:
        """Get application faults (crashes) reported by VDAs.

        ApplicationFaults has no Application navigation property — its fields
        are Id, FaultingApplicationPath, ProcessName, SessionKey, Version,
        Description, FaultReportedDate, BrowserNames, MachineId, with Session/
        Machine nav properties only. `app_name` matches against ProcessName.
        """
        filters = []
        if app_name:
            filters.append(f"contains(ProcessName, {_odata_quote(app_name)})")

        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"FaultReportedDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "ApplicationFaults",
            filter=combined_filter,
            orderby="FaultReportedDate desc",
        )

    def get_application_errors(
        self, app_name: str | None = None, days: int = 7
    ) -> list[dict[str, Any]]:
        """Get application error log entries (distinct from ApplicationFaults).

        ApplicationErrors has no Application navigation property either —
        same field shape as ApplicationFaults but with ErrorReportedDate.
        `app_name` matches against ProcessName.
        """
        filters = []
        if app_name:
            filters.append(f"contains(ProcessName, {_odata_quote(app_name)})")

        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"ErrorReportedDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "ApplicationErrors",
            filter=combined_filter,
            orderby="ErrorReportedDate desc",
        )

    def get_application_activity_summary(
        self, app_name: str | None = None, days: int = 7
    ) -> list[dict[str, Any]]:
        """Get application usage rollups by time period."""
        filters = []
        if app_name:
            filters.append(f"Application/Name eq {_odata_quote(app_name)}")

        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"SummaryDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "ApplicationActivitySummaries",
            filter=combined_filter,
            expand=["Application"],
            orderby="SummaryDate desc",
        )

    # =========================================================================
    # User methods
    # =========================================================================

    def list_users(self, filter: str | None = None) -> list[dict[str, Any]]:
        """List users."""
        return self.query("Users", filter=filter)

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        """Get user by ID."""
        return self.query_single("Users", user_id)

    def get_user_by_name(self, username: str) -> dict[str, Any] | None:
        """Get user by username."""
        users = self.query("Users", filter=f"UserName eq {_odata_quote(username)}", top=1)
        return users[0] if users else None

    def get_user_sessions(
        self, user_id: int | None = None, username: str | None = None
    ) -> list[dict[str, Any]]:
        """Get sessions for a user."""
        if username:
            user = self.get_user_by_name(username)
            if user:
                user_id = user.get("Id")

        if not user_id:
            return []

        return self.query(
            "Sessions",
            filter=f"UserId eq {_odata_key(user_id)}",
            expand=["Machine"],
            orderby="StartDate desc",
        )

    # =========================================================================
    # Analytics/Infrastructure methods
    # =========================================================================

    def list_delivery_groups(self) -> list[dict[str, Any]]:
        """List delivery groups."""
        return self.query("DesktopGroups")

    def list_hypervisors(self) -> list[dict[str, Any]]:
        """List hypervisors/hosts."""
        return self.query("Hypervisors")

    def get_load_indexes(
        self, machine_id: str | None = None, machine_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Get load index data for machines."""
        if machine_name:
            machine = self.get_machine_by_name(machine_name)
            if machine:
                machine_id = machine.get("Id")

        filter = f"MachineId eq {_odata_key(machine_id)}" if machine_id else None
        return self.query(
            "LoadIndexes",
            filter=filter,
            orderby="CreatedDate desc",
        )

    def get_failure_summary(
        self, delivery_group: str | None = None, days: int = 7
    ) -> list[dict[str, Any]]:
        """Get failure summary counts."""
        filters = []
        if delivery_group:
            filters.append(f"DesktopGroup/Name eq {_odata_quote(delivery_group)}")

        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"SummaryDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "FailureLogSummaries",
            filter=combined_filter,
            expand=["DesktopGroup"],
            orderby="SummaryDate desc",
        )

    def get_load_index_summary(
        self,
        machine_id: str | None = None,
        machine_name: str | None = None,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get load index averages by time period and machine."""
        if machine_name:
            machine = self.get_machine_by_name(machine_name)
            if machine:
                machine_id = machine.get("Id")

        filters = []
        if machine_id:
            filters.append(f"MachineId eq {_odata_key(machine_id)}")

        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"SummaryDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "LoadIndexSummaries",
            filter=combined_filter,
            orderby="SummaryDate desc",
        )

    # Process utilization granularity -> OData entity name
    _PROCESS_UTIL_ENTITIES = {
        "raw": "ProcessUtilization",
        "minute": "ProcessUtilizationMinuteSummary",
        "hour": "ProcessUtilizationHourSummary",
        "day": "ProcessUtilizationDaySummary",
    }

    def get_process_utilization(
        self,
        machine_id: str | None = None,
        machine_name: str | None = None,
        granularity: str = "raw",
        days: int = 1,
        filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get per-process CPU/memory utilization on a machine.

        granularity: "raw" (per-sample), "minute", "hour", or "day" summary.
        """
        if machine_name:
            machine = self.get_machine_by_name(machine_name)
            if machine:
                machine_id = machine.get("Id")

        entity = self._PROCESS_UTIL_ENTITIES.get(granularity, "ProcessUtilization")
        date_field = "CollectedDate" if entity == "ProcessUtilization" else "SummaryDate"

        filters = []
        if filter:
            filters.append(filter)
        if machine_id:
            filters.append(f"MachineId eq {_odata_key(machine_id)}")

        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None).isoformat() + "Z"
        filters.append(f"{date_field} ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(entity, filter=combined_filter, orderby=f"{date_field} desc")

    def list_probe_rules(self, filter: str | None = None) -> list[dict[str, Any]]:
        """List configured application probes."""
        return self.query("ProbeRules", filter=filter)

    def list_probe_endpoints(self, filter: str | None = None) -> list[dict[str, Any]]:
        """List machines running the Citrix Probe Agent."""
        return self.query("ProbeEndpoints", filter=filter)

    def list_probe_results(self, filter: str | None = None, top: int | None = None) -> list[dict[str, Any]]:
        """List probe run results, including failure stage."""
        return self.query("ProbeResults", filter=filter, top=top)

    def list_task_logs(self, filter: str | None = None, top: int | None = None) -> list[dict[str, Any]]:
        """List internal Monitor Service task/job execution logs."""
        return self.query("TaskLogs", filter=filter, top=top)


# Global client instance
_client: CitrixMonitorClient | None = None


def get_client() -> CitrixMonitorClient:
    """Get or create the global client instance."""
    global _client
    if _client is None:
        _client = CitrixMonitorClient()
    return _client
