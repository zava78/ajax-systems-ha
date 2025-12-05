"""Button platform for Ajax Systems via Jeedom MQTT."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_JEEDOM_CMD_ARM,
    CONF_JEEDOM_CMD_DISARM,
    CONF_JEEDOM_CMD_NIGHT_MODE,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import AjaxDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ajax button controls via Jeedom MQTT."""
    coordinator: AjaxDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Only create buttons if Jeedom MQTT is enabled and command IDs are configured
    if not coordinator.jeedom_mqtt_handler:
        _LOGGER.debug("Jeedom MQTT not enabled, skipping button setup")
        return
    
    config_data = {**entry.data, **entry.options}
    
    # Get command IDs from config
    cmd_arm = config_data.get(CONF_JEEDOM_CMD_ARM)
    cmd_disarm = config_data.get(CONF_JEEDOM_CMD_DISARM)
    cmd_night = config_data.get(CONF_JEEDOM_CMD_NIGHT_MODE)
    
    entities: list[ButtonEntity] = []
    
    if cmd_arm:
        entities.append(AjaxArmButton(coordinator, cmd_arm))
        _LOGGER.debug("Created ARM button with command ID: %s", cmd_arm)
    
    if cmd_disarm:
        entities.append(AjaxDisarmButton(coordinator, cmd_disarm))
        _LOGGER.debug("Created DISARM button with command ID: %s", cmd_disarm)
    
    if cmd_night:
        entities.append(AjaxNightModeButton(coordinator, cmd_night))
        _LOGGER.debug("Created NIGHT MODE button with command ID: %s", cmd_night)
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d Ajax control buttons", len(entities))
    else:
        _LOGGER.info("No Jeedom command IDs configured, buttons not created")


class AjaxJeedomButton(CoordinatorEntity[AjaxDataCoordinator], ButtonEntity):
    """Base class for Ajax control buttons via Jeedom MQTT."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        command_id: str,
        button_name: str,
        icon: str,
        payload: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._command_id = command_id
        self._payload = payload
        
        hub = coordinator.data.hub
        hub_id = hub.device_id if hub else "ajax_hub"
        hub_name = hub.name if hub else "Ajax Hub"
        
        self._attr_unique_id = f"{hub_id}_jeedom_{button_name.lower().replace(' ', '_')}"
        self._attr_name = button_name
        self._attr_icon = icon
        
        # Device info - link to the Ajax Hub
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub_id)},
            name=hub_name,
            manufacturer=MANUFACTURER,
            model=hub.device_type if hub else "Hub 2",
            via_device=(DOMAIN, hub_id),
        )
    
    async def async_press(self) -> None:
        """Handle button press - publish command to Jeedom MQTT."""
        try:
            topic = f"jeedom/cmd/set/{self._command_id}"
            
            _LOGGER.info(
                "Button pressed: %s - Publishing to %s with payload: %s",
                self._attr_name,
                topic,
                self._payload
            )
            
            await mqtt.async_publish(
                self.hass,
                topic,
                self._payload,
                qos=0,
                retain=False,
            )
            
            _LOGGER.debug("Command sent successfully")
            
        except Exception as err:
            _LOGGER.error("Failed to send command: %s", err)


class AjaxArmButton(AjaxJeedomButton):
    """Button to arm the Ajax alarm via Jeedom."""
    
    def __init__(self, coordinator: AjaxDataCoordinator, command_id: str) -> None:
        """Initialize ARM button."""
        super().__init__(
            coordinator=coordinator,
            command_id=command_id,
            button_name="Arm Alarm",
            icon="mdi:shield-lock",
            payload="ARM",
        )


class AjaxDisarmButton(AjaxJeedomButton):
    """Button to disarm the Ajax alarm via Jeedom."""
    
    def __init__(self, coordinator: AjaxDataCoordinator, command_id: str) -> None:
        """Initialize DISARM button."""
        super().__init__(
            coordinator=coordinator,
            command_id=command_id,
            button_name="Disarm Alarm",
            icon="mdi:shield-off",
            payload="DISARM",
        )


class AjaxNightModeButton(AjaxJeedomButton):
    """Button to set Ajax alarm to night mode via Jeedom."""
    
    def __init__(self, coordinator: AjaxDataCoordinator, command_id: str) -> None:
        """Initialize NIGHT MODE button."""
        super().__init__(
            coordinator=coordinator,
            command_id=command_id,
            button_name="Night Mode",
            icon="mdi:weather-night",
            payload="NIGHT_MODE",
        )
