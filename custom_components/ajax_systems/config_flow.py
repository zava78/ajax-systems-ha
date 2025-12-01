"""Config flow for Ajax Systems integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
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
    CONF_MQTT_PREFIX,
    CONF_SIA_ACCOUNT,
    CONF_SIA_ENCRYPTION_KEY,
    CONF_SIA_PORT,
    CONF_USE_CLOUD,
    CONF_USE_MQTT,
    CONF_USE_SIA,
    DEFAULT_MQTT_PREFIX,
    DEFAULT_SIA_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AjaxSystemsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ajax Systems."""
    
    VERSION = 1
    
    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._integration_type: str = ""
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose integration type."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._integration_type = user_input.get("integration_type", "sia")
            
            if self._integration_type == "sia":
                return await self.async_step_sia()
            elif self._integration_type == "cloud":
                return await self.async_step_cloud()
            elif self._integration_type == "mqtt":
                return await self.async_step_mqtt()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("integration_type", default="sia"): vol.In({
                    "sia": "SIA Protocol (Recommended)",
                    "cloud": "Ajax Cloud API (Experimental)",
                    "mqtt": "MQTT Bridge (Jeedom)",
                }),
            }),
            errors=errors,
            description_placeholders={
                "sia_description": "Receive alarm events via SIA DC-09 protocol",
                "cloud_description": "Full control via reverse-engineered API",
                "mqtt_description": "Use Jeedom MQTT bridge as fallback",
            },
        )
    
    async def async_step_sia(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure SIA protocol."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data = {
                CONF_USE_SIA: True,
                CONF_USE_CLOUD: False,
                CONF_USE_MQTT: False,
                CONF_HUB_ID: user_input.get(CONF_HUB_ID, "ajax_hub"),
                CONF_SIA_PORT: user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                CONF_SIA_ACCOUNT: user_input.get(CONF_SIA_ACCOUNT, "AAA"),
                CONF_SIA_ENCRYPTION_KEY: user_input.get(CONF_SIA_ENCRYPTION_KEY, ""),
            }
            
            # Validate port is available
            # TODO: Add port validation
            
            # Check for existing entry
            await self.async_set_unique_id(f"ajax_sia_{self._data[CONF_SIA_PORT]}")
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"Ajax SIA (Port {self._data[CONF_SIA_PORT]})",
                data=self._data,
            )
        
        return self.async_show_form(
            step_id="sia",
            data_schema=vol.Schema({
                vol.Required(CONF_HUB_ID, default="ajax_hub"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_SIA_PORT, default=DEFAULT_SIA_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Required(CONF_SIA_ACCOUNT, default="AAA"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_SIA_ENCRYPTION_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }),
            errors=errors,
        )
    
    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure Ajax Cloud API."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            username = user_input.get(CONF_USERNAME, "")
            password = user_input.get(CONF_PASSWORD, "")
            
            # Validate credentials
            from .api import AjaxCloudApi, AjaxAuthError
            
            api = AjaxCloudApi(username, password)
            try:
                if await api.authenticate():
                    self._data = {
                        CONF_USE_SIA: user_input.get(CONF_USE_SIA, True),
                        CONF_USE_CLOUD: True,
                        CONF_USE_MQTT: False,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_SIA_PORT: user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                        CONF_SIA_ACCOUNT: user_input.get(CONF_SIA_ACCOUNT, "AAA"),
                    }
                    
                    # Get hub ID from API
                    hubs = await api.get_hubs()
                    if hubs:
                        self._data[CONF_HUB_ID] = hubs[0].device_id
                    
                    await api.close()
                    
                    # Check for existing entry
                    await self.async_set_unique_id(f"ajax_cloud_{username}")
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"Ajax Cloud ({username})",
                        data=self._data,
                    )
                else:
                    errors["base"] = "auth_failed"
            except AjaxAuthError:
                errors["base"] = "auth_failed"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            finally:
                await api.close()
        
        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_USE_SIA, default=True): BooleanSelector(),
                vol.Optional(CONF_SIA_PORT, default=DEFAULT_SIA_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(CONF_SIA_ACCOUNT, default="AAA"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }),
            errors=errors,
        )
    
    async def async_step_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure MQTT bridge."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data = {
                CONF_USE_SIA: user_input.get(CONF_USE_SIA, False),
                CONF_USE_CLOUD: False,
                CONF_USE_MQTT: True,
                CONF_HUB_ID: user_input.get(CONF_HUB_ID, "ajax_hub"),
                CONF_MQTT_PREFIX: user_input.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX),
                CONF_SIA_PORT: user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
            }
            
            # Check for existing entry
            await self.async_set_unique_id(f"ajax_mqtt_{self._data[CONF_MQTT_PREFIX]}")
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"Ajax MQTT ({self._data[CONF_MQTT_PREFIX]})",
                data=self._data,
            )
        
        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema({
                vol.Required(CONF_HUB_ID, default="ajax_hub"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_MQTT_PREFIX, default=DEFAULT_MQTT_PREFIX): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_USE_SIA, default=False): BooleanSelector(),
                vol.Optional(CONF_SIA_PORT, default=DEFAULT_SIA_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
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
        return AjaxOptionsFlow(config_entry)


class AjaxOptionsFlow(OptionsFlow):
    """Handle options flow for Ajax Systems."""
    
    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
    
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SIA_PORT,
                    default=self.config_entry.data.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(
                    CONF_SIA_ACCOUNT,
                    default=self.config_entry.data.get(CONF_SIA_ACCOUNT, "AAA"),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }),
        )
