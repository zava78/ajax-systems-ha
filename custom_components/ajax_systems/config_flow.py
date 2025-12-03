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
    CONF_MQTT_PREFIX,
    CONF_MQTT_PUBLISH_ENABLED,
    CONF_MQTT_PUBLISH_PREFIX,
    CONF_MQTT_PUBLISH_ATTRIBUTES,
    CONF_MQTT_PUBLISH_RETAIN,
    CONF_MQTT_DISCOVERY_ENABLED,
    CONF_JEEDOM_MQTT_ENABLED,
    CONF_JEEDOM_MQTT_TOPIC,
    CONF_JEEDOM_MQTT_LANGUAGE,
    CONF_SIA_ACCOUNT,
    CONF_SIA_ENCRYPTION_KEY,
    CONF_SIA_PORT,
    CONF_USE_MQTT,
    CONF_USE_SIA,
    CONF_USE_JEEDOM_PROXY,
    CONF_JEEDOM_HOST,
    CONF_JEEDOM_PORT,
    CONF_JEEDOM_USE_SSL,
    CONF_JEEDOM_API_KEY,
    CONF_AJAX_USERNAME,
    CONF_AJAX_PASSWORD,
    DEFAULT_MQTT_PREFIX,
    DEFAULT_MQTT_PUBLISH_PREFIX,
    DEFAULT_SIA_PORT,
    DEFAULT_JEEDOM_PORT,
    DEFAULT_JEEDOM_PORT_SSL,
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
            elif self._integration_type == "jeedom_mqtt":
                return await self.async_step_jeedom_mqtt()
            elif self._integration_type == "jeedom":
                return await self.async_step_jeedom()
            elif self._integration_type == "mqtt":
                return await self.async_step_mqtt()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("integration_type", default="sia"): vol.In({
                    "sia": "SIA Protocol (Recommended - Local)",
                    "jeedom_mqtt": "📡 Jeedom MQTT (Recommended)",
                    "jeedom": "🔌 Jeedom Server API (Full Control)",
                    "mqtt": "MQTT Bridge (Legacy)",
                }),
            }),
            errors=errors,
            description_placeholders={
                "sia_description": "Receive alarm events via SIA DC-09 protocol",
                "jeedom_mqtt_description": "Receive sensor states from Jeedom via MQTT",
                "jeedom_description": "Full control via local/remote Jeedom server",
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
                CONF_USE_MQTT: False,
                CONF_HUB_ID: user_input.get(CONF_HUB_ID, "ajax_hub"),
                CONF_SIA_PORT: user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                CONF_SIA_ACCOUNT: user_input.get(CONF_SIA_ACCOUNT, "AAA"),
                CONF_SIA_ENCRYPTION_KEY: user_input.get(CONF_SIA_ENCRYPTION_KEY, ""),
                # MQTT Publish options
                CONF_MQTT_PUBLISH_ENABLED: user_input.get(CONF_MQTT_PUBLISH_ENABLED, False),
                CONF_MQTT_PUBLISH_PREFIX: user_input.get(CONF_MQTT_PUBLISH_PREFIX, DEFAULT_MQTT_PUBLISH_PREFIX),
                CONF_MQTT_PUBLISH_ATTRIBUTES: user_input.get(CONF_MQTT_PUBLISH_ATTRIBUTES, True),
                CONF_MQTT_DISCOVERY_ENABLED: user_input.get(CONF_MQTT_DISCOVERY_ENABLED, False),
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
                # MQTT Publish options
                vol.Optional(CONF_MQTT_PUBLISH_ENABLED, default=False): BooleanSelector(),
                vol.Optional(CONF_MQTT_PUBLISH_PREFIX, default=DEFAULT_MQTT_PUBLISH_PREFIX): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_MQTT_PUBLISH_ATTRIBUTES, default=True): BooleanSelector(),
                vol.Optional(CONF_MQTT_DISCOVERY_ENABLED, default=False): BooleanSelector(),
            }),
            errors=errors,
        )
    
    async def async_step_jeedom_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure Jeedom MQTT subscription."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            mqtt_topic = user_input.get(CONF_JEEDOM_MQTT_TOPIC, DEFAULT_JEEDOM_MQTT_TOPIC)
            language = user_input.get(CONF_JEEDOM_MQTT_LANGUAGE, "it")
            
            self._data = {
                CONF_USE_SIA: user_input.get(CONF_USE_SIA, False),
                CONF_USE_MQTT: False,
                CONF_JEEDOM_MQTT_ENABLED: True,
                CONF_JEEDOM_MQTT_TOPIC: mqtt_topic,
                CONF_JEEDOM_MQTT_LANGUAGE: language,
                CONF_HUB_ID: user_input.get(CONF_HUB_ID, "ajax_hub"),
                CONF_SIA_PORT: user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                CONF_SIA_ACCOUNT: user_input.get(CONF_SIA_ACCOUNT, "AAA"),
                # MQTT Publish options
                CONF_MQTT_PUBLISH_ENABLED: user_input.get(CONF_MQTT_PUBLISH_ENABLED, False),
                CONF_MQTT_PUBLISH_PREFIX: user_input.get(CONF_MQTT_PUBLISH_PREFIX, DEFAULT_MQTT_PUBLISH_PREFIX),
                CONF_MQTT_PUBLISH_ATTRIBUTES: user_input.get(CONF_MQTT_PUBLISH_ATTRIBUTES, True),
                CONF_MQTT_DISCOVERY_ENABLED: user_input.get(CONF_MQTT_DISCOVERY_ENABLED, False),
            }
            
            # Check for existing entry
            await self.async_set_unique_id(f"ajax_jeedom_mqtt_{mqtt_topic.replace('/', '_')}")
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"Ajax Jeedom MQTT ({mqtt_topic})",
                data=self._data,
            )
        
        return self.async_show_form(
            step_id="jeedom_mqtt",
            data_schema=vol.Schema({
                vol.Required(CONF_JEEDOM_MQTT_TOPIC, default=DEFAULT_JEEDOM_MQTT_TOPIC): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_JEEDOM_MQTT_LANGUAGE, default="it"): vol.In({
                    "it": "Italiano",
                    "en": "English",
                }),
                vol.Required(CONF_HUB_ID, default="ajax_hub"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_USE_SIA, default=False): BooleanSelector(),
                vol.Optional(CONF_SIA_PORT, default=DEFAULT_SIA_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(CONF_SIA_ACCOUNT, default="AAA"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                # MQTT Publish options
                vol.Optional(CONF_MQTT_PUBLISH_ENABLED, default=False): BooleanSelector(),
                vol.Optional(CONF_MQTT_PUBLISH_PREFIX, default=DEFAULT_MQTT_PUBLISH_PREFIX): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_MQTT_PUBLISH_ATTRIBUTES, default=True): BooleanSelector(),
                vol.Optional(CONF_MQTT_DISCOVERY_ENABLED, default=False): BooleanSelector(),
            }),
            errors=errors,
            description_placeholders={
                "jeedom_mqtt_note": "Subscribe to Jeedom MQTT events to receive Ajax sensor states. Requires Jeedom with ajaxSystem plugin publishing to MQTT.",
            },
        )
    
    async def async_step_jeedom(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure Jeedom Server Connection."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            jeedom_host = user_input.get(CONF_JEEDOM_HOST, "")
            jeedom_port = user_input.get(CONF_JEEDOM_PORT, DEFAULT_JEEDOM_PORT)
            jeedom_use_ssl = user_input.get(CONF_JEEDOM_USE_SSL, False)
            jeedom_api_key = user_input.get(CONF_JEEDOM_API_KEY, "")
            ajax_username = user_input.get(CONF_AJAX_USERNAME, "")
            ajax_password = user_input.get(CONF_AJAX_PASSWORD, "")
            
            # Try to authenticate
            try:
                from .api.jeedom_proxy import (
                    JeedomAjaxProxy,
                    JeedomAuthError,
                    JeedomConnectionError,
                )
                
                proxy = JeedomAjaxProxy(
                    jeedom_host=jeedom_host,
                    jeedom_port=jeedom_port,
                    jeedom_use_ssl=jeedom_use_ssl,
                    jeedom_api_key=jeedom_api_key,
                    ajax_username=ajax_username,
                    ajax_password=ajax_password,
                )
                
                try:
                    await proxy.authenticate()
                    hubs = await proxy.get_hubs()
                    _LOGGER.info("Jeedom Proxy: Found %d hubs", len(hubs))
                    
                    if not hubs:
                        errors["base"] = "no_hubs"
                        
                except JeedomAuthError as err:
                    _LOGGER.error("Jeedom auth failed: %s", err)
                    errors["base"] = "invalid_jeedom_auth"
                except JeedomConnectionError as err:
                    _LOGGER.error("Jeedom connection error: %s", err)
                    errors["base"] = "cannot_connect"
                except Exception as err:
                    error_str = str(err)
                    _LOGGER.error("Jeedom error: %s", error_str)
                    # Check for specific error types
                    if "404" in error_str:
                        errors["base"] = "jeedom_service_unavailable"
                    elif "401" in error_str or "403" in error_str:
                        errors["base"] = "invalid_jeedom_auth"
                    else:
                        errors["base"] = "jeedom_proxy_error"
                finally:
                    await proxy.close()
                    
            except ImportError as err:
                _LOGGER.error("Failed to import Jeedom proxy: %s", err)
                errors["base"] = "unknown"
            
            if not errors:
                self._data = {
                    CONF_USE_SIA: user_input.get(CONF_USE_SIA, True),
                    CONF_USE_MQTT: False,
                    CONF_USE_JEEDOM_PROXY: True,
                    CONF_JEEDOM_HOST: jeedom_host,
                    CONF_JEEDOM_PORT: jeedom_port,
                    CONF_JEEDOM_USE_SSL: jeedom_use_ssl,
                    CONF_JEEDOM_API_KEY: jeedom_api_key,
                    CONF_AJAX_USERNAME: ajax_username,
                    CONF_AJAX_PASSWORD: ajax_password,
                    CONF_HUB_ID: user_input.get(CONF_HUB_ID, "ajax_hub"),
                    CONF_SIA_PORT: user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                    CONF_SIA_ACCOUNT: user_input.get(CONF_SIA_ACCOUNT, "AAA"),
                    # MQTT Publish options
                    CONF_MQTT_PUBLISH_ENABLED: user_input.get(CONF_MQTT_PUBLISH_ENABLED, False),
                    CONF_MQTT_PUBLISH_PREFIX: user_input.get(CONF_MQTT_PUBLISH_PREFIX, DEFAULT_MQTT_PUBLISH_PREFIX),
                    CONF_MQTT_PUBLISH_ATTRIBUTES: user_input.get(CONF_MQTT_PUBLISH_ATTRIBUTES, True),
                    CONF_MQTT_DISCOVERY_ENABLED: user_input.get(CONF_MQTT_DISCOVERY_ENABLED, False),
                }
                
                await self.async_set_unique_id(f"ajax_jeedom_{jeedom_host}_{ajax_username}")
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"Ajax via Jeedom ({jeedom_host})",
                    data=self._data,
                )
        
        return self.async_show_form(
            step_id="jeedom",
            data_schema=vol.Schema({
                vol.Required(CONF_JEEDOM_HOST, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_JEEDOM_PORT, default=DEFAULT_JEEDOM_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(CONF_JEEDOM_USE_SSL, default=False): BooleanSelector(),
                vol.Required(CONF_JEEDOM_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_AJAX_USERNAME): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_AJAX_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_HUB_ID, default="ajax_hub"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_USE_SIA, default=True): BooleanSelector(),
                vol.Optional(CONF_SIA_PORT, default=DEFAULT_SIA_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(CONF_SIA_ACCOUNT, default="AAA"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                # MQTT Publish options
                vol.Optional(CONF_MQTT_PUBLISH_ENABLED, default=False): BooleanSelector(),
                vol.Optional(CONF_MQTT_PUBLISH_PREFIX, default=DEFAULT_MQTT_PUBLISH_PREFIX): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_MQTT_PUBLISH_ATTRIBUTES, default=True): BooleanSelector(),
                vol.Optional(CONF_MQTT_DISCOVERY_ENABLED, default=False): BooleanSelector(),
            }),
            errors=errors,
            description_placeholders={
                "jeedom_note": "Requires a local or remote Jeedom server with the ajaxSystem plugin installed. Enter the Jeedom server IP/hostname, port, and API key.",
            },
        )
    
    async def async_step_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure MQTT bridge."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data = {
                CONF_USE_SIA: user_input.get(CONF_USE_SIA, False),
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
                # MQTT Publish options
                vol.Optional(
                    CONF_MQTT_PUBLISH_ENABLED,
                    default=current_data.get(CONF_MQTT_PUBLISH_ENABLED, False),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_MQTT_PUBLISH_PREFIX,
                    default=current_data.get(CONF_MQTT_PUBLISH_PREFIX, DEFAULT_MQTT_PUBLISH_PREFIX),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_MQTT_PUBLISH_ATTRIBUTES,
                    default=current_data.get(CONF_MQTT_PUBLISH_ATTRIBUTES, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_MQTT_DISCOVERY_ENABLED,
                    default=current_data.get(CONF_MQTT_DISCOVERY_ENABLED, False),
                ): BooleanSelector(),
            }),
        )
