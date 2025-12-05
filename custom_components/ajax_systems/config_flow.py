"""Config flow for Ajax Systems integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_HUB_ID,
    CONF_JEEDOM_CMD_ARM,
    CONF_JEEDOM_CMD_DISARM,
    CONF_JEEDOM_CMD_NIGHT_MODE,
    CONF_JEEDOM_MQTT_ENABLED,
    CONF_JEEDOM_MQTT_TOPIC,
    CONF_JEEDOM_MQTT_LANGUAGE,
    CONF_SIA_ACCOUNT,
    CONF_SIA_ENCRYPTION_KEY,
    CONF_SIA_PORT,
    CONF_USE_MQTT,
    CONF_USE_SIA,
    DEFAULT_SIA_PORT,
    DEFAULT_JEEDOM_MQTT_TOPIC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AjaxSystemsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ajax Systems."""
    
    VERSION = 1
    
    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - configure MQTT Bridge directly."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            mqtt_topic = user_input.get(CONF_JEEDOM_MQTT_TOPIC, DEFAULT_JEEDOM_MQTT_TOPIC)
            language = user_input.get(CONF_JEEDOM_MQTT_LANGUAGE, "it")
            use_sia = user_input.get(CONF_USE_SIA, False)
            hub_id = user_input.get(CONF_HUB_ID, "ajax_hub")
            
            self._data = {
                CONF_USE_SIA: use_sia,
                CONF_USE_MQTT: True,
                CONF_JEEDOM_MQTT_ENABLED: True,
                CONF_JEEDOM_MQTT_TOPIC: mqtt_topic,
                CONF_JEEDOM_MQTT_LANGUAGE: language,
                CONF_HUB_ID: hub_id,
            }
            
            # Add SIA config if enabled
            if use_sia:
                self._data[CONF_SIA_PORT] = user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT)
                self._data[CONF_SIA_ACCOUNT] = user_input.get(CONF_SIA_ACCOUNT, "AAA")
                self._data[CONF_SIA_ENCRYPTION_KEY] = user_input.get(CONF_SIA_ENCRYPTION_KEY, "")
            
            # Check for existing entry
            await self.async_set_unique_id(f"ajax_mqtt_{mqtt_topic.replace('/', '_')}")
            self._abort_if_unique_id_configured()
            
            title = f"Ajax MQTT ({hub_id})"
            if use_sia:
                sia_port = self._data.get(CONF_SIA_PORT, DEFAULT_SIA_PORT)
                title = f"Ajax MQTT + SIA ({hub_id})"
            
            return self.async_create_entry(
                title=title,
                data=self._data,
            )
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HUB_ID, default="ajax_hub"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_JEEDOM_MQTT_TOPIC, default=DEFAULT_JEEDOM_MQTT_TOPIC): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_JEEDOM_MQTT_LANGUAGE, default="it"): vol.In({
                    "it": "Italiano",
                    "en": "English",
                }),
                vol.Optional(CONF_USE_SIA, default=False): BooleanSelector(),
                vol.Optional(CONF_SIA_PORT, default=DEFAULT_SIA_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(CONF_SIA_ACCOUNT, default="AAA"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_SIA_ENCRYPTION_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }),
            errors=errors,
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return AjaxOptionsFlow()


class AjaxOptionsFlow(OptionsFlow):
    """Handle options flow for Ajax Systems."""
    
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        # Get current values from config entry
        current_data = {**self.config_entry.data, **self.config_entry.options}
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_JEEDOM_MQTT_TOPIC,
                    default=current_data.get(CONF_JEEDOM_MQTT_TOPIC, DEFAULT_JEEDOM_MQTT_TOPIC),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_JEEDOM_MQTT_LANGUAGE,
                    default=current_data.get(CONF_JEEDOM_MQTT_LANGUAGE, "it"),
                ): vol.In({
                    "it": "Italiano",
                    "en": "English",
                }),
                vol.Optional(
                    CONF_JEEDOM_CMD_ARM,
                    description={"suggested_value": current_data.get(CONF_JEEDOM_CMD_ARM, "")},
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_JEEDOM_CMD_DISARM,
                    description={"suggested_value": current_data.get(CONF_JEEDOM_CMD_DISARM, "")},
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_JEEDOM_CMD_NIGHT_MODE,
                    description={"suggested_value": current_data.get(CONF_JEEDOM_CMD_NIGHT_MODE, "")},
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_USE_SIA,
                    default=current_data.get(CONF_USE_SIA, False),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SIA_PORT,
                    default=current_data.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(
                    CONF_SIA_ACCOUNT,
                    default=current_data.get(CONF_SIA_ACCOUNT, "AAA"),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }),
        )
