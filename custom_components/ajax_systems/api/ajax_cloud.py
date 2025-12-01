"""Ajax Systems Cloud API client.

This module implements a reverse-engineered client for the Ajax Systems cloud API.
Based on analysis of the Jeedom plugin and mobile app communications.

WARNING: This API is not officially documented and may change without notice.
"""
import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from ..const import (
    AJAX_CLOUD_BASE_URL,
    API_TIMEOUT,
    AjaxAlarmState,
    AjaxCommand,
    AjaxDeviceType,
)
from ..models import (
    AjaxDevice,
    AjaxDoorSensor,
    AjaxFireSensor,
    AjaxHub,
    AjaxLeakSensor,
    AjaxMotionSensor,
)

_LOGGER = logging.getLogger(__name__)


class AjaxApiError(Exception):
    """Base exception for Ajax API errors."""


class AjaxAuthError(AjaxApiError):
    """Authentication error."""


class AjaxConnectionError(AjaxApiError):
    """Connection error."""


class AjaxCloudApi:
    """Ajax Systems Cloud API client.
    
    This client attempts to communicate with Ajax cloud services.
    Note: Ajax does not provide a public API, so this is based on
    reverse engineering and may not work or may break at any time.
    """
    
    # Known API endpoints (discovered through analysis)
    ENDPOINTS = {
        "login": "/api/account/login",
        "refresh": "/api/account/refresh",
        "hubs": "/api/hubs",
        "hub_info": "/api/hubs/{hub_id}",
        "devices": "/api/hubs/{hub_id}/devices",
        "device_info": "/api/hubs/{hub_id}/devices/{device_id}",
        "arm": "/api/hubs/{hub_id}/arm",
        "disarm": "/api/hubs/{hub_id}/disarm",
        "night_mode": "/api/hubs/{hub_id}/night",
        "events": "/api/hubs/{hub_id}/events",
        "sync": "/api/sync",
    }
    
    def __init__(
        self,
        username: str,
        password: str,
        session: Optional[ClientSession] = None,
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._session = session
        self._own_session = session is None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._user_id: Optional[str] = None
        self._hubs: dict[str, AjaxHub] = {}
        self._devices: dict[str, AjaxDevice] = {}
        
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
    
    def _get_headers(self, authenticated: bool = True) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Ajax-HomeAssistant/1.0",
            "X-App-Version": "2.0.0",
        }
        if authenticated and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        authenticated: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """Make an API request."""
        session = await self._get_session()
        url = f"{AJAX_CLOUD_BASE_URL}{endpoint}"
        headers = self._get_headers(authenticated)
        
        try:
            async with session.request(
                method,
                url,
                json=data,
                headers=headers,
                **kwargs,
            ) as response:
                if response.status == 401:
                    if authenticated and self._refresh_token:
                        await self._refresh_auth()
                        return await self._request(
                            method, endpoint, data, authenticated, **kwargs
                        )
                    raise AjaxAuthError("Authentication failed")
                
                if response.status == 403:
                    raise AjaxAuthError("Access forbidden")
                
                if response.status >= 400:
                    text = await response.text()
                    raise AjaxApiError(f"API error {response.status}: {text}")
                
                return await response.json()
                
        except aiohttp.ClientError as err:
            raise AjaxConnectionError(f"Connection error: {err}") from err
    
    async def authenticate(self) -> bool:
        """Authenticate with Ajax cloud.
        
        Note: Ajax uses a complex authentication flow that may include:
        - Email/password login
        - 2FA verification
        - Device registration
        
        This implementation attempts basic auth which may not work.
        """
        _LOGGER.debug("Attempting Ajax cloud authentication")
        
        try:
            # Attempt login
            response = await self._request(
                "POST",
                self.ENDPOINTS["login"],
                data={
                    "email": self._username,
                    "password": self._password,
                    "remember": True,
                },
                authenticated=False,
            )
            
            self._access_token = response.get("accessToken")
            self._refresh_token = response.get("refreshToken")
            self._user_id = response.get("userId")
            
            expires_in = response.get("expiresIn", 3600)
            self._token_expires = datetime.now() + timedelta(seconds=expires_in)
            
            _LOGGER.info("Successfully authenticated with Ajax cloud")
            return True
            
        except AjaxApiError as err:
            _LOGGER.warning(
                "Ajax cloud authentication failed: %s. "
                "The cloud API may not be available. "
                "Consider using SIA or MQTT bridge instead.",
                err,
            )
            return False
    
    async def _refresh_auth(self) -> bool:
        """Refresh authentication token."""
        if not self._refresh_token:
            return await self.authenticate()
        
        try:
            response = await self._request(
                "POST",
                self.ENDPOINTS["refresh"],
                data={"refreshToken": self._refresh_token},
                authenticated=False,
            )
            
            self._access_token = response.get("accessToken")
            self._refresh_token = response.get("refreshToken", self._refresh_token)
            
            expires_in = response.get("expiresIn", 3600)
            self._token_expires = datetime.now() + timedelta(seconds=expires_in)
            
            return True
            
        except AjaxApiError:
            return await self.authenticate()
    
    async def get_hubs(self) -> list[AjaxHub]:
        """Get list of hubs associated with account."""
        if not self._access_token:
            await self.authenticate()
        
        try:
            response = await self._request("GET", self.ENDPOINTS["hubs"])
            hubs = []
            
            for hub_data in response.get("hubs", []):
                hub = self._parse_hub(hub_data)
                self._hubs[hub.device_id] = hub
                hubs.append(hub)
            
            return hubs
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to get hubs: %s", err)
            return []
    
    async def get_hub_info(self, hub_id: str) -> Optional[AjaxHub]:
        """Get detailed hub information."""
        endpoint = self.ENDPOINTS["hub_info"].format(hub_id=hub_id)
        
        try:
            response = await self._request("GET", endpoint)
            hub = self._parse_hub(response)
            self._hubs[hub.device_id] = hub
            return hub
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to get hub info: %s", err)
            return self._hubs.get(hub_id)
    
    async def get_devices(self, hub_id: str) -> list[AjaxDevice]:
        """Get devices for a hub."""
        endpoint = self.ENDPOINTS["devices"].format(hub_id=hub_id)
        
        try:
            response = await self._request("GET", endpoint)
            devices = []
            
            for device_data in response.get("devices", []):
                device = self._parse_device(device_data, hub_id)
                if device:
                    self._devices[device.device_id] = device
                    devices.append(device)
            
            return devices
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to get devices: %s", err)
            return list(self._devices.values())
    
    async def arm(self, hub_id: str) -> bool:
        """Arm the alarm (away mode)."""
        endpoint = self.ENDPOINTS["arm"].format(hub_id=hub_id)
        
        try:
            await self._request("POST", endpoint, data={"mode": "full"})
            if hub_id in self._hubs:
                self._hubs[hub_id].state = AjaxAlarmState.ARMED_AWAY
            return True
        except AjaxApiError as err:
            _LOGGER.error("Failed to arm: %s", err)
            return False
    
    async def disarm(self, hub_id: str) -> bool:
        """Disarm the alarm."""
        endpoint = self.ENDPOINTS["disarm"].format(hub_id=hub_id)
        
        try:
            await self._request("POST", endpoint)
            if hub_id in self._hubs:
                self._hubs[hub_id].state = AjaxAlarmState.DISARMED
            return True
        except AjaxApiError as err:
            _LOGGER.error("Failed to disarm: %s", err)
            return False
    
    async def night_mode(self, hub_id: str) -> bool:
        """Set night mode (home/partial arm)."""
        endpoint = self.ENDPOINTS["night_mode"].format(hub_id=hub_id)
        
        try:
            await self._request("POST", endpoint)
            if hub_id in self._hubs:
                self._hubs[hub_id].state = AjaxAlarmState.ARMED_HOME
            return True
        except AjaxApiError as err:
            _LOGGER.error("Failed to set night mode: %s", err)
            return False
    
    async def send_command(self, hub_id: str, command: AjaxCommand) -> bool:
        """Send a command to the hub."""
        if command == AjaxCommand.ARM:
            return await self.arm(hub_id)
        elif command == AjaxCommand.DISARM:
            return await self.disarm(hub_id)
        elif command == AjaxCommand.NIGHT_MODE:
            return await self.night_mode(hub_id)
        else:
            _LOGGER.warning("Unknown command: %s", command)
            return False
    
    def _parse_hub(self, data: dict[str, Any]) -> AjaxHub:
        """Parse hub data from API response."""
        # Map API state to our state enum
        state_map = {
            "disarmed": AjaxAlarmState.DISARMED,
            "armed": AjaxAlarmState.ARMED_AWAY,
            "full": AjaxAlarmState.ARMED_AWAY,
            "night": AjaxAlarmState.ARMED_HOME,
            "partial": AjaxAlarmState.ARMED_HOME,
            "arming": AjaxAlarmState.ARMING,
            "triggered": AjaxAlarmState.TRIGGERED,
        }
        
        raw_state = data.get("state", "disarmed").lower()
        state = state_map.get(raw_state, AjaxAlarmState.DISARMED)
        
        # Determine hub type
        model = data.get("model", "Hub")
        hub_type = AjaxDeviceType.HUB
        if "2 Plus" in model or "2+" in model:
            hub_type = AjaxDeviceType.HUB_2_PLUS
        elif "2" in model:
            hub_type = AjaxDeviceType.HUB_2
        elif "Hybrid" in model:
            hub_type = AjaxDeviceType.HUB_HYBRID
        
        return AjaxHub(
            device_id=str(data.get("id", data.get("hubId", ""))),
            device_type=hub_type,
            name=data.get("name", "Ajax Hub"),
            hub_id=str(data.get("id", data.get("hubId", ""))),
            online=data.get("online", True),
            battery_level=data.get("battery"),
            signal_strength=data.get("signalLevel"),
            firmware_version=data.get("firmware"),
            state=state,
            gsm_signal=data.get("gsmSignal"),
            ethernet_connected=data.get("ethernet", False),
            wifi_connected=data.get("wifi", False),
            external_power=data.get("externalPower", True),
            last_event=data.get("lastEvent"),
        )
    
    def _parse_device(
        self, data: dict[str, Any], hub_id: str
    ) -> Optional[AjaxDevice]:
        """Parse device data from API response."""
        device_type_str = data.get("type", "").lower()
        device_id = str(data.get("id", data.get("deviceId", "")))
        name = data.get("name", f"Ajax {device_type_str}")
        
        # Common attributes
        common = {
            "device_id": device_id,
            "name": name,
            "hub_id": hub_id,
            "online": data.get("online", True),
            "battery_level": data.get("battery"),
            "signal_strength": data.get("signalLevel"),
            "temperature": data.get("temperature"),
            "firmware_version": data.get("firmware"),
            "tamper": data.get("tamper", False),
        }
        
        # Create appropriate device type
        if "door" in device_type_str or "opening" in device_type_str:
            device_type = AjaxDeviceType.DOOR_PROTECT
            if "plus" in device_type_str:
                device_type = AjaxDeviceType.DOOR_PROTECT_PLUS
            return AjaxDoorSensor(
                **common,
                device_type=device_type,
                is_open=data.get("opened", data.get("open", False)),
            )
        
        elif "motion" in device_type_str or "pir" in device_type_str:
            device_type = AjaxDeviceType.MOTION_PROTECT
            if "plus" in device_type_str:
                device_type = AjaxDeviceType.MOTION_PROTECT_PLUS
            elif "cam" in device_type_str:
                device_type = AjaxDeviceType.MOTION_CAM
            elif "outdoor" in device_type_str:
                device_type = AjaxDeviceType.MOTION_PROTECT_OUTDOOR
            return AjaxMotionSensor(
                **common,
                device_type=device_type,
                motion_detected=data.get("motion", False),
            )
        
        elif "leak" in device_type_str or "water" in device_type_str:
            return AjaxLeakSensor(
                **common,
                device_type=AjaxDeviceType.LEAKS_PROTECT,
                leak_detected=data.get("leak", data.get("alarm", False)),
            )
        
        elif "fire" in device_type_str or "smoke" in device_type_str:
            device_type = AjaxDeviceType.FIRE_PROTECT
            if "plus" in device_type_str:
                device_type = AjaxDeviceType.FIRE_PROTECT_PLUS
            elif "2" in device_type_str:
                device_type = AjaxDeviceType.FIRE_PROTECT_2
            return AjaxFireSensor(
                **common,
                device_type=device_type,
                smoke_detected=data.get("smoke", False),
                heat_detected=data.get("heat", False),
                co_detected=data.get("co", False),
            )
        
        elif "glass" in device_type_str:
            return AjaxDevice(
                **common,
                device_type=AjaxDeviceType.GLASS_PROTECT,
            )
        
        else:
            # Generic device
            _LOGGER.debug("Unknown device type: %s", device_type_str)
            return AjaxDevice(
                **common,
                device_type=AjaxDeviceType.HUB,  # Default
            )
    
    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        if not self._access_token:
            return False
        if self._token_expires and datetime.now() >= self._token_expires:
            return False
        return True
    
    @property
    def hubs(self) -> dict[str, AjaxHub]:
        """Get cached hubs."""
        return self._hubs
    
    @property
    def devices(self) -> dict[str, AjaxDevice]:
        """Get cached devices."""
        return self._devices
