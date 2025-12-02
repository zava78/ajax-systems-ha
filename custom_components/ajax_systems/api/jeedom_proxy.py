"""Ajax Systems API client via Jeedom Cloud Proxy.

This module provides access to Ajax Systems devices through the Jeedom Market
cloud proxy. This requires valid Jeedom Market credentials.

IMPORTANT: This uses the Jeedom cloud infrastructure. You need:
1. A Jeedom Market account (market.jeedom.com)
2. Your Ajax Systems app credentials

The Jeedom cloud acts as a proxy to the Ajax API, providing:
- Authentication handling
- Token refresh
- Event callbacks (webhooks)

CREDITS:
- Based on Jeedom ajaxSystem plugin by Jeedom SAS
- https://github.com/jeedom/plugin-ajaxSystem
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from ..const import API_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# Jeedom Cloud endpoints
JEEDOM_CLOUD_URL = "https://market.jeedom.com"
AJAX_SERVICE_PATH = "/service/ajaxSystem"


class JeedomProxyError(Exception):
    """Base exception for Jeedom proxy errors."""
    pass


class JeedomAuthError(JeedomProxyError):
    """Authentication error with Jeedom Market."""
    pass


class JeedomConnectionError(JeedomProxyError):
    """Connection error with Jeedom cloud."""
    pass


@dataclass
class AjaxHubData:
    """Ajax Hub data from Jeedom proxy."""
    hub_id: str
    name: str
    color: str = "white"
    hub_subtype: str = "HUB_2"
    ip: Optional[str] = None
    firmware: Optional[str] = None
    state: str = "DISARMED"
    battery_level: Optional[int] = None
    gsm_signal: Optional[str] = None
    externally_powered: bool = True
    tampered: bool = False
    online: bool = True


@dataclass
class AjaxDeviceData:
    """Ajax Device data from Jeedom proxy."""
    device_id: str
    hub_id: str
    name: str
    device_type: str
    color: str = "white"
    firmware: Optional[str] = None
    online: bool = True
    battery_level: Optional[int] = None
    signal_level: Optional[str] = None
    temperature: Optional[float] = None
    tampered: bool = False
    # Device-specific states
    reed_closed: Optional[bool] = None  # Door sensors
    motion_detected: Optional[bool] = None  # Motion sensors
    smoke_detected: Optional[bool] = None  # Fire sensors
    leak_detected: Optional[bool] = None  # Leak sensors


class JeedomAjaxProxy:
    """Ajax Systems API client via Jeedom Cloud proxy."""
    
    def __init__(
        self,
        jeedom_username: str,
        jeedom_password: str,
        ajax_username: str,
        ajax_password: str,
        callback_url: Optional[str] = None,
        session: Optional[ClientSession] = None,
    ) -> None:
        """Initialize the Jeedom proxy client.
        
        Args:
            jeedom_username: Jeedom Market email
            jeedom_password: Jeedom Market password
            ajax_username: Ajax Systems app email
            ajax_password: Ajax Systems app password
            callback_url: External URL for event callbacks (optional)
            session: aiohttp session (optional)
        """
        self._jeedom_username = jeedom_username
        self._jeedom_password = jeedom_password
        self._ajax_username = ajax_username
        self._ajax_password = ajax_password
        self._callback_url = callback_url
        
        self._session = session
        self._own_session = session is None
        
        # Auth state
        self._user_id: Optional[str] = None
        self._session_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._authenticated = False
        
        # Cached data
        self._hubs: dict[str, AjaxHubData] = {}
        self._devices: dict[str, AjaxDeviceData] = {}
    
    def _get_auth_header(self) -> str:
        """Generate Jeedom Market authorization header."""
        # Jeedom uses SHA-512 of lowercase(username:password)
        auth_string = f"{self._jeedom_username.lower()}:{self._jeedom_password}"
        return hashlib.sha512(auth_string.encode()).hexdigest()
    
    async def _get_session(self) -> ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=API_TIMEOUT)
            self._session = ClientSession(timeout=timeout)
            self._own_session = True
        return self._session
    
    async def close(self) -> None:
        """Close the API client."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()
    
    async def _request(
        self,
        path: str,
        data: Optional[dict] = None,
        method: str = "GET",
    ) -> dict[str, Any]:
        """Make a request to Jeedom Cloud proxy.
        
        Args:
            path: API path (e.g., '/user/{userId}/hubs')
            data: Request data (optional)
            method: HTTP method
            
        Returns:
            Response data dict
        """
        session = await self._get_session()
        
        # Build URL
        url = f"{JEEDOM_CLOUD_URL}{AJAX_SERVICE_PATH}"
        
        # Replace {userId} placeholder
        if self._user_id:
            path = path.replace("{userId}", self._user_id)
        
        params = {"path": path}
        
        # Add session token for authenticated requests
        if path not in ["/login", "/refresh"] and self._session_token:
            params["session_token"] = self._session_token
        
        # Add data for GET requests
        if data and method == "GET":
            params["options"] = json.dumps(data)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": self._get_auth_header(),
        }
        
        _LOGGER.debug("Jeedom proxy request: %s %s", method, path)
        
        try:
            kwargs: dict[str, Any] = {
                "headers": headers,
                "params": params,
            }
            
            if data and method in ["POST", "PUT"]:
                kwargs["json"] = data
            
            async with session.request(method, url, **kwargs) as response:
                text = await response.text()
                _LOGGER.debug("Jeedom proxy response: %s", text[:500])
                
                if response.status == 401:
                    raise JeedomAuthError("Invalid Jeedom Market credentials")
                
                if response.status == 403:
                    raise JeedomAuthError("Access denied - check Jeedom subscription")
                
                if response.status != 200:
                    raise JeedomProxyError(f"HTTP {response.status}: {text}")
                
                result = json.loads(text)
                
                # Handle errors in response
                if isinstance(result, dict):
                    if "error" in result or "errors" in result:
                        error_msg = result.get("error") or result.get("errors")
                        raise JeedomProxyError(f"API error: {error_msg}")
                    
                    # Return body if present
                    if "body" in result:
                        return result["body"]
                
                return result
                
        except aiohttp.ClientError as err:
            raise JeedomConnectionError(f"Connection error: {err}") from err
        except json.JSONDecodeError as err:
            raise JeedomProxyError(f"Invalid JSON response: {err}") from err
    
    async def authenticate(self) -> bool:
        """Authenticate with Ajax Systems via Jeedom proxy.
        
        Returns:
            True if authentication successful
        """
        _LOGGER.info("Authenticating with Jeedom proxy for Ajax Systems")
        
        try:
            # Generate API key (could be random, but let's use a hash)
            api_key = hashlib.md5(
                f"{self._ajax_username}:{datetime.now().isoformat()}".encode()
            ).hexdigest()
            
            data = {
                "login": self._ajax_username,
                "passwordHash": self._ajax_password,  # May need to be hashed
                "userRole": "USER",
                "apikey": api_key,
            }
            
            # Add callback URL if provided
            if self._callback_url:
                data["url"] = self._callback_url
            
            response = await self._request("/login", data, "POST")
            
            self._session_token = response.get("sessionToken")
            self._refresh_token = response.get("refreshToken")
            self._user_id = response.get("userId")
            
            if not self._session_token or not self._user_id:
                raise JeedomAuthError("Missing tokens in login response")
            
            self._authenticated = True
            _LOGGER.info("Successfully authenticated with Jeedom proxy")
            return True
            
        except JeedomProxyError:
            raise
        except Exception as err:
            raise JeedomAuthError(f"Authentication failed: {err}") from err
    
    async def refresh_token(self) -> bool:
        """Refresh the session token.
        
        Returns:
            True if refresh successful
        """
        if not self._refresh_token or not self._user_id:
            return await self.authenticate()
        
        try:
            data = {
                "userId": self._user_id,
                "refreshToken": self._refresh_token,
            }
            
            response = await self._request("/refresh", data, "POST")
            
            self._session_token = response.get("sessionToken")
            new_refresh = response.get("refreshToken")
            if new_refresh:
                self._refresh_token = new_refresh
            
            _LOGGER.debug("Token refreshed successfully")
            return True
            
        except Exception as err:
            _LOGGER.warning("Token refresh failed: %s, re-authenticating", err)
            return await self.authenticate()
    
    async def get_hubs(self) -> list[AjaxHubData]:
        """Get list of Ajax hubs.
        
        Returns:
            List of hub data
        """
        if not self._authenticated:
            await self.authenticate()
        
        try:
            hubs_list = await self._request("/user/{userId}/hubs")
            
            hubs = []
            for hub_basic in hubs_list:
                hub_id = hub_basic.get("hubId")
                if not hub_id:
                    continue
                
                # Get detailed hub info
                hub_info = await self._request(f"/user/{{userId}}/hubs/{hub_id}")
                
                hub = AjaxHubData(
                    hub_id=hub_id,
                    name=hub_info.get("name", f"Ajax Hub {hub_id}"),
                    color=hub_info.get("color", "white"),
                    hub_subtype=hub_info.get("hubSubtype", "HUB_2"),
                    ip=hub_info.get("ethernet", {}).get("ip"),
                    firmware=hub_info.get("firmware", {}).get("version"),
                    state=hub_info.get("state", "DISARMED"),
                    battery_level=hub_info.get("battery", {}).get("chargeLevelPercentage"),
                    gsm_signal=hub_info.get("gsm", {}).get("signalLevel"),
                    externally_powered=hub_info.get("externallyPowered", True),
                    tampered=hub_info.get("tampered", False),
                    online=hub_info.get("online", True),
                )
                
                self._hubs[hub_id] = hub
                hubs.append(hub)
                
                _LOGGER.info("Found hub: %s (%s)", hub.name, hub.hub_id)
            
            return hubs
            
        except JeedomProxyError:
            raise
        except Exception as err:
            _LOGGER.error("Failed to get hubs: %s", err)
            return list(self._hubs.values())
    
    async def get_devices(self, hub_id: str) -> list[AjaxDeviceData]:
        """Get devices for a hub.
        
        Args:
            hub_id: Hub ID
            
        Returns:
            List of device data
        """
        if not self._authenticated:
            await self.authenticate()
        
        try:
            devices_list = await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/devices"
            )
            
            devices = []
            for device_basic in devices_list:
                device_id = device_basic.get("id")
                if not device_id:
                    continue
                
                # Get detailed device info
                device_info = await self._request(
                    f"/user/{{userId}}/hubs/{hub_id}/devices/{device_id}"
                )
                
                device = AjaxDeviceData(
                    device_id=device_id,
                    hub_id=hub_id,
                    name=device_info.get("deviceName", f"Device {device_id}"),
                    device_type=device_info.get("deviceType", "unknown"),
                    color=device_info.get("color", "white"),
                    firmware=device_info.get("firmwareVersion"),
                    online=device_info.get("online", True),
                    battery_level=device_info.get("batteryChargeLevelPercentage"),
                    signal_level=device_info.get("signalLevel"),
                    temperature=device_info.get("temperature"),
                    tampered=device_info.get("tampered", False),
                    reed_closed=device_info.get("reedClosed"),
                    motion_detected=None,  # Derived from events
                    smoke_detected=None,
                    leak_detected=None,
                )
                
                self._devices[device_id] = device
                devices.append(device)
                
                _LOGGER.info(
                    "Found device: %s (%s) - %s",
                    device.name, device.device_type, device.device_id
                )
            
            return devices
            
        except JeedomProxyError:
            raise
        except Exception as err:
            _LOGGER.error("Failed to get devices for hub %s: %s", hub_id, err)
            return [d for d in self._devices.values() if d.hub_id == hub_id]
    
    async def get_groups(self, hub_id: str) -> list[dict]:
        """Get security groups for a hub.
        
        Args:
            hub_id: Hub ID
            
        Returns:
            List of group data
        """
        if not self._authenticated:
            await self.authenticate()
        
        try:
            return await self._request(f"/user/{{userId}}/hubs/{hub_id}/groups")
        except Exception as err:
            _LOGGER.error("Failed to get groups: %s", err)
            return []
    
    async def arm(self, hub_id: str, ignore_problems: bool = True) -> bool:
        """Arm the alarm system.
        
        Args:
            hub_id: Hub ID
            ignore_problems: Ignore open zones
            
        Returns:
            True if successful
        """
        try:
            await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/commands/arming",
                {"command": "ARM", "ignoreProblems": ignore_problems},
                "PUT",
            )
            
            if hub_id in self._hubs:
                self._hubs[hub_id].state = "ARMED"
            
            _LOGGER.info("Armed hub %s", hub_id)
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to arm: %s", err)
            return False
    
    async def disarm(self, hub_id: str) -> bool:
        """Disarm the alarm system.
        
        Args:
            hub_id: Hub ID
            
        Returns:
            True if successful
        """
        try:
            await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/commands/arming",
                {"command": "DISARM", "ignoreProblems": True},
                "PUT",
            )
            
            if hub_id in self._hubs:
                self._hubs[hub_id].state = "DISARMED"
            
            _LOGGER.info("Disarmed hub %s", hub_id)
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to disarm: %s", err)
            return False
    
    async def night_mode(self, hub_id: str) -> bool:
        """Enable night mode (partial arm).
        
        Args:
            hub_id: Hub ID
            
        Returns:
            True if successful
        """
        try:
            await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/commands/arming",
                {"command": "NIGHT_MODE_ON", "ignoreProblems": True},
                "PUT",
            )
            
            if hub_id in self._hubs:
                self._hubs[hub_id].state = "NIGHT_MODE"
            
            _LOGGER.info("Night mode enabled for hub %s", hub_id)
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to enable night mode: %s", err)
            return False
    
    async def panic(self, hub_id: str) -> bool:
        """Send panic alarm.
        
        Args:
            hub_id: Hub ID
            
        Returns:
            True if successful
        """
        try:
            await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/commands/panic",
                {
                    "location": {
                        "latitude": 0,
                        "longitude": 0,
                        "accuracy": 0,
                        "speed": 0,
                        "timestamp": 0,
                    }
                },
                "PUT",
            )
            
            _LOGGER.warning("Panic alarm sent for hub %s", hub_id)
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to send panic: %s", err)
            return False
    
    async def mute_fire_detectors(self, hub_id: str) -> bool:
        """Mute fire detectors.
        
        Args:
            hub_id: Hub ID
            
        Returns:
            True if successful
        """
        try:
            await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/commands/muteFireDetectors",
                {"muteType": "ALL_FIRE_DETECTORS"},
                "PUT",
            )
            
            _LOGGER.info("Fire detectors muted for hub %s", hub_id)
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to mute fire detectors: %s", err)
            return False
    
    async def arm_group(self, hub_id: str, group_id: str) -> bool:
        """Arm a security group.
        
        Args:
            hub_id: Hub ID
            group_id: Group ID
            
        Returns:
            True if successful
        """
        try:
            await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/groups/{group_id}/commands/arming",
                {"command": "ARM", "ignoreProblems": True},
                "PUT",
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to arm group: %s", err)
            return False
    
    async def disarm_group(self, hub_id: str, group_id: str) -> bool:
        """Disarm a security group."""
        try:
            await self._request(
                f"/user/{{userId}}/hubs/{hub_id}/groups/{group_id}/commands/arming",
                {"command": "DISARM", "ignoreProblems": True},
                "PUT",
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to disarm group: %s", err)
            return False
    
    @property
    def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return self._authenticated
    
    @property
    def hubs(self) -> dict[str, AjaxHubData]:
        """Get cached hubs."""
        return self._hubs
    
    @property
    def devices(self) -> dict[str, AjaxDeviceData]:
        """Get cached devices."""
        return self._devices
