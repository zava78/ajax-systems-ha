"""Ajax Systems Cloud API client.

This module implements a reverse-engineered client for the Ajax Systems cloud API.

CREDITS & RESOURCES:
====================
- Original PHP library: https://github.com/igormukhingmailcom/ajax-systems-api
  Author: Igor Mukhin (igormukhingmailcom)
  License: MIT
  
- Jeedom Ajax plugin: https://github.com/Flobul/Jeedom-ajax
  Author: Flobul
  
- Ajax Systems official: https://ajax.systems/
- Ajax Enterprise API info: https://ajax.systems/blog/enterprise-api/
- Ajax Cloud Signaling: https://ajax.systems/ajax-cloud-signaling/

WARNING: This API was reported as "closed in 2018" but may still work.
The API is not officially documented and may change without notice.
Ajax Systems does not provide a public API for consumers.

API Base URL: https://app.ajax.systems
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from http.cookies import SimpleCookie

import aiohttp
from aiohttp import ClientSession, ClientTimeout, CookieJar

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
    
    This client uses endpoints discovered from:
    https://github.com/igormukhingmailcom/ajax-systems-api
    
    Base URL: https://app.ajax.systems
    
    Note: The original PHP library reported this API was "closed in 2018"
    but it may still work with the app.ajax.systems domain.
    """
    
    # Real API endpoints from igormukhingmailcom/ajax-systems-api
    ENDPOINTS = {
        # Authentication
        "login": "/api/account/do_login",
        "user_data": "/SecurConfig/api/account/getUserData",
        "csa_connection": "/SecurConfig/api/account/getCsaConnection",
        # Hub operations
        "hubs_data": "/SecurConfig/api/dashboard/getHubsData",
        "set_arm": "/SecurConfig/api/dashboard/setArm",
        "send_panic": "/SecurConfig/api/dashboard/sendPanic",
        "hub_balance": "/SecurConfig/api/dashboard/getHubBalance",
        "logs": "/SecurConfig/api/dashboard/getLogs",
        "send_command": "/SecurConfig/api/dashboard/sendCommand",
    }
    
    # Arm states from the PHP library
    ARM_STATE_DISARMED = 0
    ARM_STATE_ARMED = 1
    ARM_STATE_PARTIAL = 2
    
    # Wall switch commands
    COMMAND_SWITCH_ON = 6
    COMMAND_SWITCH_OFF = 7
    
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
        self._cookie_jar: Optional[CookieJar] = None
        self._authenticated = False
        self._user_id: Optional[str] = None
        self._user_data: Optional[dict] = None
        self._hubs: dict[str, AjaxHub] = {}
        self._devices: dict[str, AjaxDevice] = {}
        
    async def _get_session(self) -> ClientSession:
        """Get or create aiohttp session with cookie support."""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=API_TIMEOUT)
            # Use cookie jar to maintain session (like PHP library does)
            self._cookie_jar = CookieJar()
            self._session = ClientSession(
                timeout=timeout,
                cookie_jar=self._cookie_jar,
            )
            self._own_session = True
        return self._session
    
    async def close(self) -> None:
        """Close the API client."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()
    
    def _get_headers(self, form_data: bool = False) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; Ajax-HomeAssistant/1.0)",
        }
        if form_data:
            headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        else:
            headers["Content-Type"] = "application/json"
        return headers
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        form_data: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Make an API request."""
        session = await self._get_session()
        url = f"{AJAX_CLOUD_BASE_URL}{endpoint}"
        headers = self._get_headers(form_data)
        
        try:
            request_kwargs = {"headers": headers, **kwargs}
            
            if data:
                if form_data:
                    request_kwargs["data"] = data
                else:
                    request_kwargs["json"] = data
            
            _LOGGER.debug("API request: %s %s", method, url)
            
            async with session.request(method, url, **request_kwargs) as response:
                _LOGGER.debug("API response status: %s", response.status)
                
                # Login returns 302 redirect on success
                if response.status in [200, 302]:
                    try:
                        content = await response.text()
                        if content:
                            return {"requestResult": True, "data": content}
                        return {"requestResult": True}
                    except:
                        return {"requestResult": True}
                
                if response.status == 401 or response.status == 403:
                    raise AjaxAuthError("Authentication failed")
                
                text = await response.text()
                raise AjaxApiError(f"API error {response.status}: {text}")
                
        except aiohttp.ClientError as err:
            raise AjaxConnectionError(f"Connection error: {err}") from err
    
    async def authenticate(self) -> bool:
        """Authenticate with Ajax cloud.
        
        Uses the same flow as the PHP library:
        1. POST to /api/account/do_login with j_username and j_password
        2. On success (302 or 200), session cookies are set
        3. Call getCsaConnection to establish the connection
        """
        _LOGGER.info("Attempting Ajax cloud authentication for %s", self._username)
        
        try:
            # Step 1: Login with form data (like PHP library)
            login_data = {
                "j_username": self._username,
                "j_password": self._password,
            }
            
            response = await self._request(
                "POST",
                self.ENDPOINTS["login"],
                data=login_data,
                form_data=True,
            )
            
            if not response.get("requestResult"):
                raise AjaxAuthError("Login failed: invalid response")
            
            _LOGGER.debug("Login successful, establishing CSA connection...")
            
            # Step 2: Get CSA connection (required before other API calls)
            await self._get_csa_connection()
            
            self._authenticated = True
            _LOGGER.info("Successfully authenticated with Ajax cloud")
            return True
            
        except AjaxAuthError:
            raise
        except AjaxApiError as err:
            _LOGGER.error("Ajax cloud authentication failed: %s", err)
            raise AjaxAuthError(f"Authentication failed: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error during authentication: %s", err)
            raise AjaxAuthError(f"Authentication failed: {err}") from err
    
    async def _get_csa_connection(self) -> None:
        """Establish CSA connection (required after login)."""
        response = await self._request(
            "POST",
            self.ENDPOINTS["csa_connection"],
        )
        _LOGGER.debug("CSA connection response: %s", response)
    
    async def get_user_data(self) -> dict:
        """Get logged in user data."""
        response = await self._request(
            "GET",
            self.ENDPOINTS["user_data"],
        )
        if "data" in response:
            import json
            try:
                self._user_data = json.loads(response["data"])
            except:
                self._user_data = response["data"]
        return self._user_data or {}
    
    async def get_hubs(self) -> list[AjaxHub]:
        """Get list of hubs associated with account.
        
        Requires getCsaConnection to be called first (done in authenticate).
        """
        if not self._authenticated:
            await self.authenticate()
        
        try:
            response = await self._request(
                "POST",
                self.ENDPOINTS["hubs_data"],
            )
            
            hubs = []
            data = response.get("data")
            
            _LOGGER.debug("Raw hubs data: %s", data[:500] if data and len(data) > 500 else data)
            
            if data:
                import json
                try:
                    hub_list = json.loads(data) if isinstance(data, str) else data
                    _LOGGER.debug("Parsed hub data type: %s", type(hub_list))
                except Exception as e:
                    _LOGGER.error("Failed to parse hub data: %s", e)
                    hub_list = []
                
                if isinstance(hub_list, list):
                    for hub_data in hub_list:
                        _LOGGER.debug("Hub data keys: %s", hub_data.keys() if isinstance(hub_data, dict) else "not a dict")
                        hub = self._parse_hub(hub_data)
                        self._hubs[hub.device_id] = hub
                        hubs.append(hub)
                        # Also parse devices from hub data
                        self._parse_devices_from_hub(hub_data, hub.device_id)
                elif isinstance(hub_list, dict):
                    _LOGGER.debug("Hub data keys: %s", hub_list.keys())
                    hub = self._parse_hub(hub_list)
                    self._hubs[hub.device_id] = hub
                    hubs.append(hub)
                    # Also parse devices from hub data
                    self._parse_devices_from_hub(hub_list, hub.device_id)
            
            _LOGGER.info("Found %d hubs and %d devices", len(hubs), len(self._devices))
            return hubs
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to get hubs: %s", err)
            return list(self._hubs.values())
    
    def _parse_devices_from_hub(self, hub_data: dict, hub_id: str) -> None:
        """Extract and parse devices from hub data."""
        # Try different possible keys for devices in hub data
        device_keys = ["devices", "devicesList", "sensors", "zones", "objects"]
        
        for key in device_keys:
            if key in hub_data and hub_data[key]:
                devices_data = hub_data[key]
                _LOGGER.debug("Found devices under key '%s': %d items", key, 
                            len(devices_data) if isinstance(devices_data, list) else 1)
                
                if isinstance(devices_data, list):
                    for device_data in devices_data:
                        device = self._parse_device(device_data, hub_id)
                        if device:
                            self._devices[device.device_id] = device
                            _LOGGER.debug("Added device: %s (%s)", device.name, device.device_type)
                elif isinstance(devices_data, dict):
                    # Could be a dict with device IDs as keys
                    for dev_id, device_data in devices_data.items():
                        if isinstance(device_data, dict):
                            device_data["id"] = dev_id
                            device = self._parse_device(device_data, hub_id)
                            if device:
                                self._devices[device.device_id] = device
    
    async def get_hub_info(self, hub_id: str) -> Optional[AjaxHub]:
        """Get detailed hub information."""
        # Re-fetch hubs data to get updated info
        hubs = await self.get_hubs()
        return self._hubs.get(hub_id)
    
    async def get_devices(self, hub_id: str) -> list[AjaxDevice]:
        """Get devices for a hub.
        
        Note: The PHP API returns devices as part of hub data.
        """
        # Devices are typically included in the hub data
        # For now, return cached devices
        hub = self._hubs.get(hub_id)
        if hub:
            return [d for d in self._devices.values() if d.hub_id == hub_id]
        return []
    
    async def get_logs(self, hub_id: str, count: int = 10, offset: int = 0) -> list[dict]:
        """Get hub event logs."""
        try:
            response = await self._request(
                "POST",
                self.ENDPOINTS["logs"],
                data={
                    "hubId": hub_id,
                    "count": count,
                    "offset": offset,
                },
                form_data=True,
            )
            
            data = response.get("data")
            if data:
                import json
                try:
                    return json.loads(data) if isinstance(data, str) else data
                except:
                    return []
            return []
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to get logs: %s", err)
            return []
    
    async def arm(self, hub_id: str) -> bool:
        """Arm the alarm (away mode).
        
        Uses setArm with action=1 (ARM_STATE_ARMED).
        """
        try:
            response = await self._request(
                "POST",
                self.ENDPOINTS["set_arm"],
                data={
                    "hubID": hub_id,
                    "action": self.ARM_STATE_ARMED,
                },
                form_data=True,
            )
            
            if hub_id in self._hubs:
                self._hubs[hub_id].state = AjaxAlarmState.ARMED_AWAY
            
            _LOGGER.info("Hub %s armed successfully", hub_id)
            return True
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to arm: %s", err)
            return False
    
    async def disarm(self, hub_id: str) -> bool:
        """Disarm the alarm.
        
        Uses setArm with action=0 (ARM_STATE_DISARMED).
        """
        try:
            response = await self._request(
                "POST",
                self.ENDPOINTS["set_arm"],
                data={
                    "hubID": hub_id,
                    "action": self.ARM_STATE_DISARMED,
                },
                form_data=True,
            )
            
            if hub_id in self._hubs:
                self._hubs[hub_id].state = AjaxAlarmState.DISARMED
            
            _LOGGER.info("Hub %s disarmed successfully", hub_id)
            return True
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to disarm: %s", err)
            return False
    
    async def night_mode(self, hub_id: str) -> bool:
        """Set night mode (home/partial arm).
        
        Uses setArm with action=2 (ARM_STATE_PARTIAL).
        """
        try:
            response = await self._request(
                "POST",
                self.ENDPOINTS["set_arm"],
                data={
                    "hubID": hub_id,
                    "action": self.ARM_STATE_PARTIAL,
                },
                form_data=True,
            )
            
            if hub_id in self._hubs:
                self._hubs[hub_id].state = AjaxAlarmState.ARMED_HOME
            
            _LOGGER.info("Hub %s set to night mode", hub_id)
            return True
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to set night mode: %s", err)
            return False
    
    async def send_panic(self, hub_id: str) -> bool:
        """Send panic alarm to hub."""
        try:
            response = await self._request(
                "POST",
                self.ENDPOINTS["send_panic"],
                data={"hubID": hub_id},
                form_data=True,
            )
            
            _LOGGER.warning("Panic alarm sent to hub %s", hub_id)
            return True
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to send panic: %s", err)
            return False
    
    async def get_hub_balance(self, hub_id: str) -> Optional[str]:
        """Get hub SIM card balance."""
        try:
            response = await self._request(
                "GET",
                f"{self.ENDPOINTS['hub_balance']}?hubID={hub_id}",
            )
            return response.get("data")
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to get hub balance: %s", err)
            return None
    
    async def set_switch_state(
        self, hub_id: str, device_id: str, on: bool
    ) -> bool:
        """Turn on/off a WallSwitch or Socket.
        
        Args:
            hub_id: Hub ID (hex format like 00001234)
            device_id: Device ID (hex format)
            on: True to turn on, False to turn off
        """
        try:
            command = self.COMMAND_SWITCH_ON if on else self.COMMAND_SWITCH_OFF
            
            response = await self._request(
                "POST",
                self.ENDPOINTS["send_command"],
                data={
                    "hubID": hub_id,
                    "objectType": 31,  # WallSwitch type
                    "deviceID": device_id,
                    "command": command,
                },
                form_data=True,
            )
            
            _LOGGER.info("Switch %s turned %s", device_id, "on" if on else "off")
            return True
            
        except AjaxApiError as err:
            _LOGGER.error("Failed to set switch state: %s", err)
            return False
    
    async def send_command(self, hub_id: str, command: AjaxCommand) -> bool:
        """Send a command to the hub."""
        if command == AjaxCommand.ARM:
            return await self.arm(hub_id)
        elif command == AjaxCommand.DISARM:
            return await self.disarm(hub_id)
        elif command == AjaxCommand.NIGHT_MODE or command == AjaxCommand.PARTIAL_ARM:
            return await self.night_mode(hub_id)
        else:
            _LOGGER.warning("Unknown command: %s", command)
            return False
    
    def _parse_hub(self, data: dict[str, Any]) -> AjaxHub:
        """Parse hub data from API response.
        
        The PHP API returns hub data with fields like:
        - hubID or id
        - name
        - state (0=disarmed, 1=armed, 2=partial)
        - online
        - battery
        - etc.
        """
        # Map numeric state to our state enum
        raw_state = data.get("state", 0)
        if isinstance(raw_state, int):
            state_map = {
                0: AjaxAlarmState.DISARMED,
                1: AjaxAlarmState.ARMED_AWAY,
                2: AjaxAlarmState.ARMED_HOME,
            }
            state = state_map.get(raw_state, AjaxAlarmState.DISARMED)
        else:
            state_str = str(raw_state).lower()
            if state_str in ["disarmed", "0"]:
                state = AjaxAlarmState.DISARMED
            elif state_str in ["armed", "1", "full"]:
                state = AjaxAlarmState.ARMED_AWAY
            elif state_str in ["partial", "2", "night"]:
                state = AjaxAlarmState.ARMED_HOME
            else:
                state = AjaxAlarmState.DISARMED
        
        # Get hub ID - PHP API uses hubID or id
        hub_id = str(data.get("hubID", data.get("hubId", data.get("id", ""))))
        
        # Determine hub type from model
        model = data.get("model", data.get("hubName", "Hub"))
        hub_type = AjaxDeviceType.HUB
        if model:
            model_str = str(model)
            if "2 Plus" in model_str or "2+" in model_str:
                hub_type = AjaxDeviceType.HUB_2_PLUS
            elif "2" in model_str:
                hub_type = AjaxDeviceType.HUB_2
            elif "Hybrid" in model_str:
                hub_type = AjaxDeviceType.HUB_HYBRID
        
        return AjaxHub(
            device_id=hub_id,
            device_type=hub_type,
            name=data.get("name", data.get("hubName", "Ajax Hub")),
            hub_id=hub_id,
            online=data.get("online", data.get("isOnline", True)),
            battery_level=data.get("battery", data.get("batteryLevel")),
            signal_strength=data.get("signalLevel", data.get("signal")),
            firmware_version=data.get("firmware", data.get("firmwareVersion")),
            state=state,
            gsm_signal=data.get("gsmSignal", data.get("gsm")),
            ethernet_connected=data.get("ethernet", False),
            wifi_connected=data.get("wifi", False),
            external_power=data.get("externalPower", data.get("power", True)),
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
        return self._authenticated
    
    @property
    def hubs(self) -> dict[str, AjaxHub]:
        """Get cached hubs."""
        return self._hubs
    
    @property
    def devices(self) -> dict[str, AjaxDevice]:
        """Get cached devices."""
        return self._devices
