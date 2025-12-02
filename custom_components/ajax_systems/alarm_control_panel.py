"""Alarm control panel platform for Ajax Systems."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AjaxAlarmState, DOMAIN
from .coordinator import AjaxDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ajax alarm control panel."""
    coordinator: AjaxDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    if coordinator.data.hub:
        async_add_entities([AjaxAlarmPanel(coordinator)])


class AjaxAlarmPanel(CoordinatorEntity[AjaxDataCoordinator], AlarmControlPanelEntity):
    """Representation of an Ajax alarm panel."""
    
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required = False
    
    def __init__(self, coordinator: AjaxDataCoordinator) -> None:
        """Initialize the alarm panel."""
        super().__init__(coordinator)
        
        self._hub = coordinator.data.hub
        self._attr_unique_id = f"{DOMAIN}_{self._hub.device_id}"
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for MQTT publishing
        self.coordinator.register_entity_for_mqtt(self.entity_id)
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.device_id)},
            name=self._hub.name,
            manufacturer="Ajax Systems",
            model=self._hub.device_type.value,
            sw_version=self._hub.firmware_version,
        )
    
    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        hub = self.coordinator.data.hub
        if hub is None:
            return None
        
        state_map = {
            AjaxAlarmState.DISARMED: AlarmControlPanelState.DISARMED,
            AjaxAlarmState.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
            AjaxAlarmState.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
            AjaxAlarmState.ARMING: AlarmControlPanelState.ARMING,
            AjaxAlarmState.PENDING: AlarmControlPanelState.PENDING,
            AjaxAlarmState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
        }
        
        return state_map.get(hub.state, AlarmControlPanelState.DISARMED)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        hub = self.coordinator.data.hub
        attrs = {}
        
        if hub:
            if hub.last_event:
                attrs["last_event"] = hub.last_event
            if hub.last_event_time:
                attrs["last_event_time"] = hub.last_event_time.isoformat()
            if hub.battery_level is not None:
                attrs["battery_level"] = hub.battery_level
        
        return attrs
    
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the alarm."""
        _LOGGER.debug("Disarming Ajax alarm")
        if await self.coordinator.async_disarm():
            self._hub.state = AjaxAlarmState.DISARMED
            self.async_write_ha_state()
    
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the alarm in away mode."""
        _LOGGER.debug("Arming Ajax alarm (away)")
        if await self.coordinator.async_arm():
            self._hub.state = AjaxAlarmState.ARMED_AWAY
            self.async_write_ha_state()
    
    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm the alarm in night mode."""
        _LOGGER.debug("Arming Ajax alarm (night)")
        if await self.coordinator.async_arm_night():
            self._hub.state = AjaxAlarmState.ARMED_NIGHT
            self.async_write_ha_state()
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._hub = self.coordinator.data.hub
        self.async_write_ha_state()
