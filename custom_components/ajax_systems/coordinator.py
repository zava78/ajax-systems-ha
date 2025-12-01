"""Data coordinator for Ajax Systems integration."""
import asyncio
import logging
from datetime import timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AjaxCloudApi, AjaxApiError, AjaxAuthError
from .const import (
    CONF_HUB_ID,
    CONF_SIA_ACCOUNT,
    CONF_SIA_PORT,
    CONF_USE_CLOUD,
    CONF_USE_SIA,
    DEFAULT_SIA_PORT,
    DOMAIN,
)
from .models import AjaxCoordinator, AjaxDevice, AjaxHub, SiaEvent
from .sia import SiaConfig, SiaReceiver, sia_event_to_alarm_state, sia_event_to_sensor_state

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)


class AjaxDataCoordinator(DataUpdateCoordinator[AjaxCoordinator]):
    """Coordinator for Ajax Systems data updates."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        
        self.entry = entry
        self.data = AjaxCoordinator()
        
        # API client (for cloud mode)
        self._api: Optional[AjaxCloudApi] = None
        self._use_cloud = entry.data.get(CONF_USE_CLOUD, False)
        
        # SIA receiver
        self._sia_receiver: Optional[SiaReceiver] = None
        self._use_sia = entry.data.get(CONF_USE_SIA, True)
        
        # Event listeners
        self._listeners: list[callable] = []
    
    async def async_setup(self) -> bool:
        """Set up the coordinator."""
        cloud_ok = False
        sia_ok = False
        
        # Set up cloud API if enabled
        if self._use_cloud:
            username = self.entry.data.get(CONF_USERNAME)
            password = self.entry.data.get(CONF_PASSWORD)
            
            if username and password:
                self._api = AjaxCloudApi(username, password)
                try:
                    await self._api.authenticate()
                    _LOGGER.info("Connected to Ajax Cloud API")
                    # Get initial data
                    hubs = await self._api.get_hubs()
                    if hubs:
                        self.data.hub = hubs[0]
                        _LOGGER.info("Found hub: %s", self.data.hub.name)
                        devices = await self._api.get_devices(self.data.hub.device_id)
                        for device in devices:
                            self.data.devices[device.device_id] = device
                        self.data.connected = True
                        cloud_ok = True
                    else:
                        _LOGGER.warning("No hubs found in Ajax Cloud")
                except AjaxAuthError as err:
                    _LOGGER.error("Cloud API authentication failed: %s", err)
                    self._use_cloud = False
                except AjaxApiError as err:
                    _LOGGER.warning("Cloud API error: %s, will try SIA", err)
                    self._use_cloud = False
                except Exception as err:
                    _LOGGER.error("Unexpected cloud API error: %s", err)
                    self._use_cloud = False
        
        # Set up SIA receiver if enabled
        if self._use_sia:
            port = self.entry.data.get(CONF_SIA_PORT, DEFAULT_SIA_PORT)
            account = self.entry.data.get(CONF_SIA_ACCOUNT, "AAA")
            
            config = SiaConfig(port=port, account=account)
            self._sia_receiver = SiaReceiver(config, self._handle_sia_event)
            
            try:
                if await self._sia_receiver.start():
                    _LOGGER.info("SIA receiver started on port %d", port)
                    self.data.connected = True
                    sia_ok = True
                else:
                    _LOGGER.warning("SIA receiver failed to start (port %d may be in use)", port)
            except Exception as err:
                _LOGGER.warning("SIA receiver error: %s", err)
        
        # Create a default hub if we don't have one from cloud
        if self.data.hub is None:
            hub_id = self.entry.data.get(CONF_HUB_ID, "ajax_hub")
            from .const import AjaxDeviceType, AjaxAlarmState
            self.data.hub = AjaxHub(
                device_id=hub_id,
                device_type=AjaxDeviceType.HUB_2,
                name="Ajax Hub",
                hub_id=hub_id,
                state=AjaxAlarmState.DISARMED,
            )
            _LOGGER.info("Created default hub with ID: %s", hub_id)
        
        # Success if at least one method works, or if we just created a default hub
        if cloud_ok or sia_ok:
            _LOGGER.info("Ajax Systems coordinator setup complete (Cloud: %s, SIA: %s)", cloud_ok, sia_ok)
            return True
        
        # Even without cloud/SIA, allow setup with default hub for testing
        _LOGGER.warning(
            "Neither Cloud API nor SIA receiver could be started. "
            "Integration will work with limited functionality."
        )
        return True  # Allow setup anyway with default hub
    
    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        if self._api:
            await self._api.close()
        
        if self._sia_receiver:
            await self._sia_receiver.stop()
    
    async def _async_update_data(self) -> AjaxCoordinator:
        """Fetch data from Ajax."""
        if self._use_cloud and self._api:
            try:
                # Refresh hub info
                if self.data.hub:
                    hub = await self._api.get_hub_info(self.data.hub.device_id)
                    if hub:
                        self.data.hub = hub
                    
                    # Refresh device states
                    devices = await self._api.get_devices(self.data.hub.device_id)
                    for device in devices:
                        self.data.update_device(device)
                
                self.data.connected = True
                
            except AjaxAuthError:
                _LOGGER.warning("Authentication expired, re-authenticating")
                await self._api.authenticate()
            except AjaxApiError as err:
                raise UpdateFailed(f"Error fetching data: {err}") from err
        
        # SIA doesn't poll, it receives push events
        return self.data
    
    @callback
    def _handle_sia_event(self, event: SiaEvent) -> None:
        """Handle incoming SIA event."""
        _LOGGER.debug("Processing SIA event: %s", event)
        
        # Update alarm state
        new_state = sia_event_to_alarm_state(event)
        if new_state and self.data.hub:
            self.data.hub.state = new_state
            self.data.hub.last_event = event.event_code
            self.data.hub.last_event_time = event.timestamp
        
        # Update sensor state
        sensor_update = sia_event_to_sensor_state(event)
        if sensor_update:
            zone = sensor_update.get("zone")
            if zone:
                # Find device by zone or create placeholder
                device_id = f"zone_{zone}"
                if device_id in self.data.devices:
                    device = self.data.devices[device_id]
                    # Update device state based on event type
                    if hasattr(device, "is_open") and "is_open" in sensor_update:
                        device.is_open = sensor_update["is_open"]
                    if hasattr(device, "motion_detected") and "motion_detected" in sensor_update:
                        device.motion_detected = sensor_update["motion_detected"]
                    if hasattr(device, "leak_detected") and "leak_detected" in sensor_update:
                        device.leak_detected = sensor_update["leak_detected"]
                    if hasattr(device, "smoke_detected") and "smoke_detected" in sensor_update:
                        device.smoke_detected = sensor_update["smoke_detected"]
                    if "tamper" in sensor_update:
                        device.tamper = sensor_update["tamper"]
        
        # Notify listeners
        self.async_set_updated_data(self.data)
    
    async def async_arm(self) -> bool:
        """Arm the alarm."""
        if self._use_cloud and self._api and self.data.hub:
            return await self._api.arm(self.data.hub.device_id)
        _LOGGER.warning("Arm command not available without cloud API")
        return False
    
    async def async_disarm(self) -> bool:
        """Disarm the alarm."""
        if self._use_cloud and self._api and self.data.hub:
            return await self._api.disarm(self.data.hub.device_id)
        _LOGGER.warning("Disarm command not available without cloud API")
        return False
    
    async def async_arm_night(self) -> bool:
        """Set night mode."""
        if self._use_cloud and self._api and self.data.hub:
            return await self._api.night_mode(self.data.hub.device_id)
        _LOGGER.warning("Night mode command not available without cloud API")
        return False
