"""Citrix Monitor Service OData API client."""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests_ntlm import HttpNtlmAuth

# Try loading .env from multiple locations
# 1. Current working directory (default)
# 2. Package installation directory (for MCP usage)
load_dotenv()
_pkg_env = Path(__file__).parent.parent.parent / ".env"
if _pkg_env.exists():
    load_dotenv(_pkg_env)


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
                # Rate limited - wait and retry
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
    ) -> list[dict[str, Any]]:
        """Execute OData query with automatic pagination.

        Args:
            entity: Entity name (e.g., "Machines", "Sessions")
            filter: OData $filter expression
            select: List of fields to select
            orderby: OData $orderby expression
            top: Maximum records to return (per page if paginating)
            skip: Number of records to skip
            expand: List of related entities to expand
            count: Include total count in response

        Returns:
            List of entity records
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
        url = f"{self.base_url}/{entity}"

        while url:
            response = self._request_with_retry("GET", url, params=params)
            response.raise_for_status()
            data = response.json()

            results.extend(data.get("value", []))

            # Follow pagination link if present
            url = data.get("@odata.nextLink")
            params = None  # Only use params on first request

        return results

    def query_single(
        self, entity: str, key: str | int, expand: list[str] | None = None
    ) -> dict[str, Any] | None:
        """Query a single entity by key.

        Args:
            entity: Entity name
            key: Entity key value
            expand: List of related entities to expand

        Returns:
            Entity record or None if not found
        """
        params = {}
        if expand:
            params["$expand"] = ",".join(expand)

        url = f"{self.base_url}/{entity}({key})"
        response = self._request_with_retry("GET", url, params=params or None)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

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

        Args:
            entity: Entity name
            filter: Optional OData $filter expression

        Returns:
            Count of matching entities
        """
        url = f"{self.base_url}/{entity}/$count"
        params = {"$filter": filter} if filter else None

        response = self._request_with_retry("GET", url, params=params)
        response.raise_for_status()
        return int(response.text)

    # =========================================================================
    # Machine methods
    # =========================================================================

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
            filters.append(f"CurrentRegistrationState eq '{registration_state}'")
        if power_state:
            filters.append(f"CurrentPowerState eq '{power_state}'")
        if in_maintenance is not None:
            filters.append(f"IsInMaintenanceMode eq {str(in_maintenance).lower()}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query("Machines", filter=combined_filter)

    def get_machine(self, machine_id: int) -> dict[str, Any] | None:
        """Get machine by ID."""
        return self.query_single("Machines", machine_id)

    def get_machine_by_name(self, name: str) -> dict[str, Any] | None:
        """Get machine by name."""
        machines = self.query("Machines", filter=f"Name eq '{name}'", top=1)
        return machines[0] if machines else None

    def get_machine_metrics(
        self, machine_id: int | None = None, name: str | None = None
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
            filter=f"MachineId eq {machine_id}",
            orderby="CreatedDate desc",
        )

    def get_machine_failures(
        self, machine_id: int | None = None, name: str | None = None
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
            filter=f"MachineId eq {machine_id}",
            orderby="FailureStartDate desc",
        )

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
            filters.append(f"User/UserName eq '{user_name}'")
        if machine_name:
            filters.append(f"Machine/Name eq '{machine_name}'")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "Sessions",
            filter=combined_filter,
            expand=["User", "Machine"],
            orderby="StartDate desc",
        )

    def get_session(self, session_key: str) -> dict[str, Any] | None:
        """Get session by key."""
        return self.query_single("Sessions", f"'{session_key}'", expand=["User", "Machine"])

    def get_logon_metrics(self, session_key: str) -> list[dict[str, Any]]:
        """Get logon duration breakdown for a session."""
        return self.query(
            "LogOnMetrics",
            filter=f"SessionKey eq '{session_key}'",
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
            filters.append(f"SessionKey eq '{session_key}'")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "Connections",
            filter=combined_filter,
            orderby="LogOnStartDate desc",
        )

    def get_connection_failures(
        self,
        filter: str | None = None,
        delivery_group: str | None = None,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get connection failure logs."""
        filters = []
        if filter:
            filters.append(filter)
        if delivery_group:
            filters.append(f"DesktopGroup/Name eq '{delivery_group}'")

        # Default to last N days
        from datetime import datetime, timedelta
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        filters.append(f"FailureDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "ConnectionFailureLogs",
            filter=combined_filter,
            expand=["DesktopGroup"],
            orderby="FailureDate desc",
        )

    # =========================================================================
    # Application methods
    # =========================================================================

    def list_applications(self, filter: str | None = None) -> list[dict[str, Any]]:
        """List published applications."""
        return self.query("Applications", filter=filter)

    def list_app_instances(
        self,
        app_id: int | None = None,
        app_name: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List running application instances."""
        filters = []
        if app_id:
            filters.append(f"ApplicationId eq {app_id}")
        if app_name:
            filters.append(f"Application/Name eq '{app_name}'")
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
        """Get application errors/faults."""
        filters = []
        if app_name:
            filters.append(f"Application/Name eq '{app_name}'")

        from datetime import datetime, timedelta
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        filters.append(f"CreatedDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "ApplicationFaults",
            filter=combined_filter,
            expand=["Application"],
            orderby="CreatedDate desc",
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
        users = self.query("Users", filter=f"UserName eq '{username}'", top=1)
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
            filter=f"UserId eq {user_id}",
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
        self, machine_id: int | None = None, machine_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Get load index data for machines."""
        if machine_name:
            machine = self.get_machine_by_name(machine_name)
            if machine:
                machine_id = machine.get("Id")

        filter = f"MachineId eq {machine_id}" if machine_id else None
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
            filters.append(f"DesktopGroup/Name eq '{delivery_group}'")

        from datetime import datetime, timedelta
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        filters.append(f"SummaryDate ge {start_date}")

        combined_filter = " and ".join(filters) if filters else None
        return self.query(
            "FailureLogSummaries",
            filter=combined_filter,
            expand=["DesktopGroup"],
            orderby="SummaryDate desc",
        )


# Global client instance
_client: CitrixMonitorClient | None = None


def get_client() -> CitrixMonitorClient:
    """Get or create the global client instance."""
    global _client
    if _client is None:
        _client = CitrixMonitorClient()
    return _client
