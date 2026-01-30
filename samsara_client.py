"""
Samsara API client for interacting with Samsara's fleet management platform.
"""

import os
from typing import Optional, Dict, Any, List
import httpx


class SamsaraError(Exception):
    """Base exception for Samsara API errors."""
    pass


class SamsaraRateLimitError(SamsaraError):
    """Exception raised when rate limit is exceeded (429)."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class SamsaraAPIError(SamsaraError):
    """Exception raised for API errors from Samsara."""
    def __init__(self, message: str, status_code: int, response_body: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class SamsaraClient:
    """Client for interacting with the Samsara API."""
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the Samsara client.
        
        Args:
            api_token: Samsara API token. If not provided, will try to get from
                     SAMSARA_API_TOKEN environment variable.
        """
        self.api_token = api_token or os.getenv("SAMSARA_API_TOKEN")
        if not self.api_token:
            raise ValueError(
                "Samsara API token is required. Set SAMSARA_API_TOKEN environment "
                "variable or pass api_token parameter."
            )
        
        self.base_url = "https://api.samsara.com"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    
    async def list_vehicles(
        self,
        limit: Optional[int] = None,
        after: Optional[str] = None,
        parent_tag_ids: Optional[str] = None,
        tag_ids: Optional[str] = None,
        attribute_value_ids: Optional[str] = None,
        attributes: Optional[List[str]] = None,
        updated_after_time: Optional[str] = None,
        created_after_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all vehicles.
        
        Args:
            limit: The limit for how many objects will be in the response. 
                  Default and max is 512 objects.
            after: If specified, this should be the endCursor value from the 
                  previous page of results.
            parent_tag_ids: A filter based on comma-separated list of parent tag IDs.
            tag_ids: A filter based on comma-separated list of tag IDs.
            attribute_value_ids: A filter based on comma-separated list of 
                                attribute value IDs.
            attributes: A filter on the data to return entities having given 
                       attributes using name-value pair or range query.
            updated_after_time: Filter on data to have an updated at time after 
                              or equal to this specified time in RFC 3339 format.
            created_after_time: Filter on data to have a created at time after 
                              or equal to this specified time in RFC 3339 format.
        
        Returns:
            Response data from the Samsara API.
        """
        params: Dict[str, Any] = {}
        
        if limit is not None:
            params["limit"] = limit
        if after is not None:
            params["after"] = after
        if parent_tag_ids is not None:
            params["parentTagIds"] = parent_tag_ids
        if tag_ids is not None:
            params["tagIds"] = tag_ids
        if attribute_value_ids is not None:
            params["attributeValueIds"] = attribute_value_ids
        if attributes is not None:
            params["attributes"] = attributes
        if updated_after_time is not None:
            params["updatedAfterTime"] = updated_after_time
        if created_after_time is not None:
            params["createdAfterTime"] = created_after_time
        
        try:
            response = await self.client.get("/fleet/vehicles", params=params)
            
            # Handle rate limiting specifically
            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    f"Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                
                # Try to extract error details from response body
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)
            
            # Handle other HTTP errors
            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    # If we can't parse JSON, use the response text
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            # This shouldn't happen since we handle status codes above,
            # but catch it just in case
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_vehicle(self, id: str) -> Dict[str, Any]:
        """
        Retrieve a vehicle by ID (Samsara ID or external ID, e.g. maintenanceId:250020 or samsara.vin:1HGBH41JXMN109186).

        Args:
            id: ID of the vehicle. Samsara ID or external ID in key:value format.

        Returns:
            Vehicle object (VehicleResponse).
        """
        params: Dict[str, Any] = {}
        url_path = "/fleet/vehicles/{id}".replace("{id}", str(id))

        try:
            response = await self.client.get(url_path, params=params)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def update_vehicle(self, id: str, vehicle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a vehicle by ID. Pass only the fields you wish to update (UpdateVehicleRequest).

        Args:
            id: ID of the vehicle (Samsara ID or external ID, e.g. maintenanceId:250020).
            vehicle: Fields to update (no required fields; only provide fields to patch).

        Returns:
            Updated vehicle object (VehicleResponse).
        """
        url_path = "/fleet/vehicles/{id}".replace("{id}", str(id))

        try:
            response = await self.client.patch(url_path, json=vehicle)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_asset_locations(
        self,
        after: Optional[str] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        ids: Optional[str] = None,
        include_speed: Optional[bool] = None,
        include_reverse_geo: Optional[bool] = None,
        include_geofence_lookup: Optional[bool] = None,
        include_high_frequency_locations: Optional[bool] = None,
        include_external_ids: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Get location and speed data for assets.

        Args:
            after: Pagination cursor from previous response.
            limit: Number of results to return (1-512, default 512).
            start_time: Start time in RFC 3339 format.
            end_time: End time in RFC 3339 format.
            ids: Comma-separated list of asset IDs.
            include_speed: Include speed data.
            include_reverse_geo: Include street address.
            include_geofence_lookup: Include geofence information.
            include_high_frequency_locations: Include high frequency location data.
            include_external_ids: Include external IDs.

        Returns:
            Response data from the Samsara API.
        """
        params: Dict[str, Any] = {}

        if after is not None:
            params["after"] = after
        if limit is not None:
            params["limit"] = limit
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if ids is not None:
            params["ids"] = ids
        if include_speed is not None:
            params["includeSpeed"] = include_speed
        if include_reverse_geo is not None:
            params["includeReverseGeo"] = include_reverse_geo
        if include_geofence_lookup is not None:
            params["includeGeofenceLookup"] = include_geofence_lookup
        if include_high_frequency_locations is not None:
            params["includeHighFrequencyLocations"] = include_high_frequency_locations
        if include_external_ids is not None:
            params["includeExternalIds"] = include_external_ids

        try:
            response = await self.client.get("/assets/location-and-speed/stream", params=params)

            # Handle rate limiting specifically
            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass

                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    f"Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."

                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass

                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            # Handle other HTTP errors
            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None

                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass

                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_safety_events(
        self,
        start_time: str,
        end_time: Optional[str] = None,
        query_by_time_field: Optional[str] = None,
        asset_ids: Optional[str] = None,
        driver_ids: Optional[str] = None,
        tag_ids: Optional[str] = None,
        assigned_coaches: Optional[str] = None,
        behavior_labels: Optional[str] = None,
        event_states: Optional[str] = None,
        include_asset: Optional[bool] = None,
        include_driver: Optional[bool] = None,
        include_vg_only_events: Optional[bool] = None,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get safety events like harsh braking, speeding, collisions, etc.

        Args:
            start_time: RFC 3339 timestamp to begin receiving data (required).
            end_time: RFC 3339 timestamp end range.
            query_by_time_field: Query by 'updatedAtTime' or 'createdAtTime'.
            asset_ids: Comma-separated asset IDs.
            driver_ids: Comma-separated driver IDs.
            tag_ids: Comma-separated tag IDs.
            assigned_coaches: Comma-separated coach IDs.
            behavior_labels: Filter by behavior type (e.g., Acceleration, Braking, Crash, Speeding).
            event_states: Filter by state (e.g., needsReview, reviewed, coached, dismissed).
            include_asset: Include asset details in response.
            include_driver: Include driver details in response.
            include_vg_only_events: Include video-only events.
            after: Pagination cursor from previous response.

        Returns:
            Response data from the Samsara API.
        """
        params: Dict[str, Any] = {"startTime": start_time}

        if end_time is not None:
            params["endTime"] = end_time
        if query_by_time_field is not None:
            params["queryByTimeField"] = query_by_time_field
        if asset_ids is not None:
            params["assetIds"] = asset_ids
        if driver_ids is not None:
            params["driverIds"] = driver_ids
        if tag_ids is not None:
            params["tagIds"] = tag_ids
        if assigned_coaches is not None:
            params["assignedCoaches"] = assigned_coaches
        if behavior_labels is not None:
            params["behaviorLabels"] = behavior_labels
        if event_states is not None:
            params["eventStates"] = event_states
        if include_asset is not None:
            params["includeAsset"] = include_asset
        if include_driver is not None:
            params["includeDriver"] = include_driver
        if include_vg_only_events is not None:
            params["includeVgOnlyEvents"] = include_vg_only_events
        if after is not None:
            params["after"] = after

        try:
            response = await self.client.get("/safety-events/stream", params=params)

            # Handle rate limiting specifically
            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass

                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    f"Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."

                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass

                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            # Handle other HTTP errors
            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None

                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass

                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_safety_events_by_id(
        self,
        safety_event_ids: List[str],
        include_asset: Optional[bool] = None,
        include_driver: Optional[bool] = None,
        include_vg_only_events: Optional[bool] = None,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get details for specified safety events by ID. Rate limit: 5 requests/sec.

        Args:
            safety_event_ids: Required list of Samsara safety event IDs (UUIDs).
            include_asset: Include expanded asset data in response.
            include_driver: Include expanded driver data in response.
            include_vg_only_events: Include events from devices with only a Vehicle Gateway (VG).
            after: Pagination cursor from previous response.

        Returns:
            Response data from the Samsara API (SafetyEventsV2GetSafetyEventsV2ResponseBody).
        """
        params: Dict[str, Any] = {"safetyEventIds": safety_event_ids}
        if include_asset is not None:
            params["includeAsset"] = include_asset
        if include_driver is not None:
            params["includeDriver"] = include_driver
        if include_vg_only_events is not None:
            params["includeVgOnlyEvents"] = include_vg_only_events
        if after is not None:
            params["after"] = after

        try:
            response = await self.client.get("/safety-events", params=params)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Safety events by ID endpoint allows 5 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_trips(
        self,
        ids: str,
        start_time: str,
        end_time: Optional[str] = None,
        query_by: Optional[str] = None,
        completion_status: Optional[str] = None,
        include_asset: Optional[bool] = None,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get trip history for specific vehicles.

        Args:
            ids: Comma-separated list of asset IDs (up to 50, required).
            start_time: RFC 3339 timestamp to begin receiving data (required).
            end_time: RFC 3339 timestamp end range.
            query_by: Query by 'updatedAtTime' or 'tripStartTime'.
            completion_status: Filter by 'inProgress', 'completed', or 'all'.
            include_asset: Include asset details in response.
            after: Pagination cursor from previous response.

        Returns:
            Response data from the Samsara API.
        """
        params: Dict[str, Any] = {
            "ids": ids,
            "startTime": start_time,
        }

        if end_time is not None:
            params["endTime"] = end_time
        if query_by is not None:
            params["queryBy"] = query_by
        if completion_status is not None:
            params["completionStatus"] = completion_status
        if include_asset is not None:
            params["includeAsset"] = include_asset
        if after is not None:
            params["after"] = after

        try:
            response = await self.client.get("/trips/stream", params=params)

            # Handle rate limiting specifically
            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass

                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    f"Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."

                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass

                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            # Handle other HTTP errors
            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None

                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass

                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def list_drivers(
        self,
        driver_activation_status: Optional[str] = None,
        limit: Optional[int] = None,
        after: Optional[str] = None,
        parent_tag_ids: Optional[str] = None,
        tag_ids: Optional[str] = None,
        attribute_value_ids: Optional[str] = None,
        attributes: Optional[List[str]] = None,
        updated_after_time: Optional[str] = None,
        created_after_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all drivers in the organization.

        Args:
            driver_activation_status: If 'deactivated', only deactivated drivers.
                Defaults to 'active' if not provided.
            limit: The limit for how many objects will be in the response (1-512).
            after: Pagination cursor from the previous page of results.
            parent_tag_ids: Comma-separated list of parent tag IDs.
            tag_ids: Comma-separated list of tag IDs.
            attribute_value_ids: Comma-separated list of attribute value IDs.
            attributes: Filter by name-value pair or range query.
            updated_after_time: Filter by updated at time (RFC 3339).
            created_after_time: Filter by created at time (RFC 3339).

        Returns:
            Response data from the Samsara API (ListDriversResponse).
        """
        params: Dict[str, Any] = {}

        if driver_activation_status is not None:
            params["driverActivationStatus"] = driver_activation_status
        if limit is not None:
            params["limit"] = limit
        if after is not None:
            params["after"] = after
        if parent_tag_ids is not None:
            params["parentTagIds"] = parent_tag_ids
        if tag_ids is not None:
            params["tagIds"] = tag_ids
        if attribute_value_ids is not None:
            params["attributeValueIds"] = attribute_value_ids
        if attributes is not None:
            params["attributes"] = attributes
        if updated_after_time is not None:
            params["updatedAfterTime"] = updated_after_time
        if created_after_time is not None:
            params["createdAfterTime"] = created_after_time

        try:
            response = await self.client.get("/fleet/drivers", params=params)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def list_gateways(
        self,
        models: Optional[List[str]] = None,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all gateways. Rate limit: 5 requests/sec.

        Args:
            models: Filter by comma-separated list of gateway models.
            after: Pagination cursor from the previous page of results.

        Returns:
            Response data from the Samsara API (GatewaysGetGatewaysResponseBody).
        """
        params: Dict[str, Any] = {}
        if models is not None:
            params["models"] = models
        if after is not None:
            params["after"] = after

        try:
            response = await self.client.get("/gateways", params=params)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Gateways endpoint allows 5 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def create_driver(self, driver: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a driver in the organization.

        Args:
            driver: CreateDriverRequest body. Must include name, password, username.
                Optional: licenseNumber, licenseState, phone, notes, tagIds,
                externalIds, timezone, locale, and other driver settings.

        Returns:
            Newly created driver object (DriverResponse).
        """
        try:
            response = await self.client.post("/fleet/drivers", json=driver)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_driver(self, id: str) -> Dict[str, Any]:
        """
        Retrieve a driver by ID (Samsara ID or external ID, e.g. payrollId:ABFS18600).

        Args:
            id: ID of the driver. Samsara ID or external ID in key:value format.

        Returns:
            Driver object (DriverResponse).
        """
        params: Dict[str, Any] = {}
        url_path = "/fleet/drivers/{id}".replace("{id}", str(id))

        try:
            response = await self.client.get(url_path, params=params)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def update_driver(self, id: str, driver: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a driver by ID. Can update properties or set driverActivationStatus to activate/deactivate.

        Args:
            id: ID of the driver (Samsara ID or external ID, e.g. payrollId:ABFS18600).
            driver: UpdateDriverRequest body (fields to update).

        Returns:
            Updated driver object (DriverResponse).
        """
        url_path = "/fleet/drivers/{id}".replace("{id}", str(id))

        try:
            response = await self.client.patch(url_path, json=driver)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def list_tags(
        self,
        limit: Optional[int] = None,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all tags in the organization.

        Args:
            limit: Number of results (1-512, default 512).
            after: Pagination cursor from previous response.

        Returns:
            Response data from the Samsara API (ListTagsResponse).
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if after is not None:
            params["after"] = after

        try:
            response = await self.client.get("/tags", params=params)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def create_tag(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new tag in the organization.

        Args:
            body: Tag creation request body with 'name' (required) and optional
                  'parentTagId', 'addresses', 'assets', 'drivers', 'machines',
                  'sensors', 'trailers', 'vehicles'.

        Returns:
            Response data from the Samsara API (TagResponse).
        """
        try:
            response = await self.client.post("/tags", json=body)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_speeding_intervals(
        self,
        asset_ids: List[str],
        start_time: str,
        end_time: Optional[str] = None,
        query_by: Optional[str] = None,
        include_asset: Optional[bool] = None,
        include_driver_id: Optional[bool] = None,
        after: Optional[str] = None,
        severity_levels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get speeding intervals for trips.

        Returns speeding intervals for completed trips based on the time parameters.
        Rate limit: 5 requests/sec.

        Args:
            asset_ids: List of asset IDs (up to 50).
            start_time: RFC 3339 timestamp for start of query range.
            end_time: RFC 3339 timestamp for end of query range (optional).
            query_by: Compare times against 'updatedAtTime' or 'tripStartTime'.
            include_asset: Include expanded asset data.
            include_driver_id: Include driver ID in response.
            after: Pagination cursor from previous response.
            severity_levels: Filter by severity ('light', 'moderate', 'heavy', 'severe').

        Returns:
            Response data from the Samsara API.
        """
        params: Dict[str, Any] = {}
        params["assetIds"] = asset_ids
        params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if query_by is not None:
            params["queryBy"] = query_by
        if include_asset is not None:
            params["includeAsset"] = include_asset
        if include_driver_id is not None:
            params["includeDriverId"] = include_driver_id
        if after is not None:
            params["after"] = after
        if severity_levels is not None:
            params["severityLevels"] = severity_levels

        try:
            response = await self.client.get("/speeding-intervals/stream", params=params)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Speeding intervals endpoint allows 5 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_safety_settings(self) -> Dict[str, Any]:
        """
        Get safety settings for the organization.

        Rate limit: 5 requests/sec.

        Returns:
            Safety settings data from the Samsara API.
        """
        try:
            response = await self.client.get("/fleet/settings/safety")

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Safety settings endpoint allows 5 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def get_organization_info(self) -> Dict[str, Any]:
        """
        Get information about your organization.

        Returns:
            Organization info (OrganizationInfoResponse).
        """
        try:
            response = await self.client.get("/me")

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {retry_after} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {response.status_code}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {error_body['message']}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {error_body['error']}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({response.status_code}): {error_text[:200]}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {str(e)}") from e

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

