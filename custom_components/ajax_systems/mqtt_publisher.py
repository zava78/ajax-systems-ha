"""MQTT Publisher for Ajax Systems integration.

This module publishes state changes of Ajax entities to a local MQTT broker.
It allows other systems to subscribe to Ajax state changes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_ALARM_ARMING,
    STATE_ALARM_PENDING,
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class MqttPublisherConfig:
    """Configuration for MQTT publisher."""
    
    enabled: bool = False
    topic_prefix: str = "ajax"
    publish_attributes: bool = True
    retain: bool = True
    qos: int = 1
    discovery_enabled: bool = False
    discovery_prefix: str = "homeassistant"


class AjaxMqttPublisher:
    """Publishes Ajax entity states to MQTT."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        config: MqttPublisherConfig,
        hub_id: str,
    ) -> None:
        """Initialize the MQTT publisher."""
        self._hass = hass
        self._config = config
        self._hub_id = hub_id
        self._tracked_entities: set[str] = set()
        self._unsubscribe_callbacks: list = []
        self._is_running = False
    
    @property
    def is_available(self) -> bool:
        """Check if MQTT integration is available."""
        return mqtt.async_get_mqtt(self._hass) is not None
    
    async def async_start(self) -> bool:
        """Start the MQTT publisher."""
        if not self._config.enabled:
            _LOGGER.debug("MQTT publisher is disabled")
            return False
        
        if not self.is_available:
            _LOGGER.warning(
                "MQTT integration is not available. "
                "Install and configure MQTT to use this feature."
            )
            return False
        
        self._is_running = True
        _LOGGER.info(
            "MQTT publisher started with topic prefix: %s",
            self._config.topic_prefix,
        )
        
        # Publish discovery if enabled
        if self._config.discovery_enabled:
            await self._publish_discovery()
        
        return True
    
    async def async_stop(self) -> None:
        """Stop the MQTT publisher."""
        for unsubscribe in self._unsubscribe_callbacks:
            unsubscribe()
        self._unsubscribe_callbacks.clear()
        self._tracked_entities.clear()
        self._is_running = False
        _LOGGER.info("MQTT publisher stopped")
    
    def track_entity(self, entity_id: str) -> None:
        """Track state changes for an entity."""
        if entity_id in self._tracked_entities:
            return
        
        if not self._is_running:
            return
        
        self._tracked_entities.add(entity_id)
        
        @callback
        def _state_changed(event: Event) -> None:
            """Handle state change event."""
            self._hass.async_create_task(
                self._async_publish_state(event)
            )
        
        unsubscribe = async_track_state_change_event(
            self._hass,
            entity_id,
            _state_changed,
        )
        self._unsubscribe_callbacks.append(unsubscribe)
        
        _LOGGER.debug("Tracking entity: %s", entity_id)
    
    def track_entities(self, entity_ids: list[str]) -> None:
        """Track state changes for multiple entities."""
        for entity_id in entity_ids:
            self.track_entity(entity_id)
    
    async def _async_publish_state(self, event: Event) -> None:
        """Publish state change to MQTT."""
        entity_id = event.data.get("entity_id", "")
        new_state = event.data.get("new_state")
        
        if new_state is None:
            return
        
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # Optionally skip unavailable states
            pass
        
        # Build topic
        # ajax/{hub_id}/{domain}/{object_id}/state
        parts = entity_id.split(".")
        if len(parts) != 2:
            return
        
        domain, object_id = parts
        topic = f"{self._config.topic_prefix}/{self._hub_id}/{domain}/{object_id}/state"
        
        # Build payload
        payload: dict[str, Any] = {
            "entity_id": entity_id,
            "state": new_state.state,
            "last_changed": new_state.last_changed.isoformat(),
            "last_updated": new_state.last_updated.isoformat(),
        }
        
        # Add attributes if configured
        if self._config.publish_attributes and new_state.attributes:
            # Filter out large or sensitive attributes
            filtered_attrs = {}
            for key, value in new_state.attributes.items():
                if key in ("entity_picture", "supported_features"):
                    continue
                # Skip non-serializable types
                try:
                    json.dumps(value)
                    filtered_attrs[key] = value
                except (TypeError, ValueError):
                    pass
            payload["attributes"] = filtered_attrs
        
        # Publish to MQTT
        try:
            await mqtt.async_publish(
                self._hass,
                topic,
                json.dumps(payload),
                qos=self._config.qos,
                retain=self._config.retain,
            )
            _LOGGER.debug(
                "Published state to MQTT: %s = %s",
                topic,
                new_state.state,
            )
        except Exception as err:
            _LOGGER.error("Failed to publish to MQTT: %s", err)
    
    async def async_publish_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Publish a custom event to MQTT."""
        if not self._is_running:
            return
        
        topic = f"{self._config.topic_prefix}/{self._hub_id}/events/{event_type}"
        
        try:
            await mqtt.async_publish(
                self._hass,
                topic,
                json.dumps(event_data),
                qos=self._config.qos,
                retain=False,  # Events should not be retained
            )
            _LOGGER.debug("Published event to MQTT: %s", topic)
        except Exception as err:
            _LOGGER.error("Failed to publish event to MQTT: %s", err)
    
    async def async_publish_alarm_event(
        self,
        event_code: str,
        event_description: str,
        zone: str | None = None,
        device_name: str | None = None,
    ) -> None:
        """Publish an alarm event to MQTT."""
        event_data = {
            "code": event_code,
            "description": event_description,
            "timestamp": self._hass.helpers.dt.utcnow().isoformat(),
        }
        if zone:
            event_data["zone"] = zone
        if device_name:
            event_data["device"] = device_name
        
        await self.async_publish_event("alarm", event_data)
    
    async def async_publish_command_result(
        self,
        command: str,
        success: bool,
        message: str | None = None,
    ) -> None:
        """Publish command result to MQTT."""
        topic = f"{self._config.topic_prefix}/{self._hub_id}/commands/result"
        
        payload = {
            "command": command,
            "success": success,
            "timestamp": self._hass.helpers.dt.utcnow().isoformat(),
        }
        if message:
            payload["message"] = message
        
        try:
            await mqtt.async_publish(
                self._hass,
                topic,
                json.dumps(payload),
                qos=self._config.qos,
                retain=False,
            )
        except Exception as err:
            _LOGGER.error("Failed to publish command result: %s", err)
    
    async def _publish_discovery(self) -> None:
        """Publish MQTT discovery configuration."""
        if not self._config.discovery_enabled:
            return
        
        # Publish alarm panel discovery
        discovery_topic = (
            f"{self._config.discovery_prefix}/alarm_control_panel/"
            f"{self._hub_id}/config"
        )
        
        discovery_payload = {
            "name": f"Ajax {self._hub_id}",
            "unique_id": f"ajax_{self._hub_id}_alarm",
            "state_topic": (
                f"{self._config.topic_prefix}/{self._hub_id}/"
                f"alarm_control_panel/{self._hub_id}_alarm/state"
            ),
            "command_topic": (
                f"{self._config.topic_prefix}/{self._hub_id}/commands/set"
            ),
            "payload_arm_away": "ARM_AWAY",
            "payload_arm_home": "ARM_HOME",
            "payload_arm_night": "ARM_NIGHT",
            "payload_disarm": "DISARM",
            "device": {
                "identifiers": [f"ajax_{self._hub_id}"],
                "name": f"Ajax Hub {self._hub_id}",
                "manufacturer": "Ajax Systems",
                "model": "Hub",
            },
        }
        
        try:
            await mqtt.async_publish(
                self._hass,
                discovery_topic,
                json.dumps(discovery_payload),
                qos=self._config.qos,
                retain=True,
            )
            _LOGGER.info("Published MQTT discovery for alarm panel")
        except Exception as err:
            _LOGGER.error("Failed to publish discovery: %s", err)


async def async_setup_mqtt_publisher(
    hass: HomeAssistant,
    config: dict[str, Any],
    hub_id: str,
) -> AjaxMqttPublisher | None:
    """Set up the MQTT publisher from config."""
    if not config.get("mqtt_publish_enabled", False):
        return None
    
    publisher_config = MqttPublisherConfig(
        enabled=True,
        topic_prefix=config.get("mqtt_publish_prefix", "ajax"),
        publish_attributes=config.get("mqtt_publish_attributes", True),
        retain=config.get("mqtt_publish_retain", True),
        qos=config.get("mqtt_publish_qos", 1),
        discovery_enabled=config.get("mqtt_discovery_enabled", False),
        discovery_prefix=config.get("mqtt_discovery_prefix", "homeassistant"),
    )
    
    publisher = AjaxMqttPublisher(hass, publisher_config, hub_id)
    
    if await publisher.async_start():
        return publisher
    
    return None
