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
    CONF_MQTT_PUBLISH_ENABLED,
    CONF_MQTT_PUBLISH_PREFIX,
    CONF_MQTT_PUBLISH_ATTRIBUTES,
    CONF_MQTT_PUBLISH_RETAIN,
    CONF_MQTT_DISCOVERY_ENABLED,
    CONF_SIA_ACCOUNT,
    CONF_SIA_ENCRYPTION_KEY,
    CONF_SIA_PORT,
    CONF_USE_CLOUD,
    CONF_USE_MQTT,
    CONF_USE_SIA,
    CONF_USE_JEEDOM_PROXY,
    CONF_JEEDOM_USERNAME,
    CONF_JEEDOM_PASSWORD,
    CONF_AJAX_USERNAME,
    CONF_AJAX_PASSWORD,
    DEFAULT_MQTT_PREFIX,
    DEFAULT_MQTT_PUBLISH_PREFIX,
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
            elif self._integration_type == "jeedom":
                return await self.async_step_jeedom()
            elif self._integration_type == "mqtt":
                return await self.async_step_mqtt()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("integration_type", default="sia"): vol.In({
                    "sia": "SIA Protocol (Recommended - Local)",
                    "jeedom": "🔌 Jeedom Cloud Proxy (Full Control)",
                    "cloud": "⚠️ Ajax Cloud API (NOT WORKING)",
                    "mqtt": "MQTT Bridge (Jeedom)",
                }),
            }),
            errors=errors,
            description_placeholders={
                "sia_description": "Receive alarm events via SIA DC-09 protocol",
                "jeedom_description": "Full control via Jeedom Market account",
                "cloud_description": "The Cloud API was closed by Ajax in 2018",
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
    
    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure Ajax Cloud API - NOT WORKING (closed in 2018)."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Show warning that Cloud API doesn't work
            errors["base"] = "cloud_api_closed"
            
            # If user insists, try anyway (will fail)
            if user_input.get("try_anyway"):
                username = user_input.get(CONF_USERNAME, "")
                password = user_input.get(CONF_PASSWORD, "")
                
                try:
                    from .api.ajax_cloud import AjaxCloudApi, AjaxAuthError, AjaxConnectionError
                    
                    api = AjaxCloudApi(username, password)
                    try:
                        await api.authenticate()
                        hubs = await api.get_hubs()
                        if not hubs:
                            errors["base"] = "cloud_api_closed"
                        else:
                            _LOGGER.info("Cloud API: Found %d hubs", len(hubs))
                    except AjaxAuthError as err:
                        _LOGGER.error("Cloud API authentication failed: %s", err)
                        errors["base"] = "cloud_api_closed"
                    except AjaxConnectionError as err:
                        _LOGGER.error("Cloud API connection error: %s", err)
                        errors["base"] = "cannot_connect"
                    except Exception as err:
                        _LOGGER.error("Cloud API unexpected error: %s", err)
                        errors["base"] = "cloud_api_closed"
                    finally:
                        await api.close()
                        
                except ImportError as err:
                    _LOGGER.error("Failed to import API client: %s", err)
                    errors["base"] = "unknown"
                
                if not errors:
                    self._data = {
                        CONF_USE_SIA: user_input.get(CONF_USE_SIA, True),
                        CONF_USE_CLOUD: True,
                        CONF_USE_MQTT: False,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_HUB_ID: user_input.get(CONF_HUB_ID, "ajax_hub"),
                        CONF_SIA_PORT: user_input.get(CONF_SIA_PORT, DEFAULT_SIA_PORT),
                        CONF_SIA_ACCOUNT: user_input.get(CONF_SIA_ACCOUNT, "AAA"),
                    }
                    
                    await self.async_set_unique_id(f"ajax_cloud_{username}")
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"Ajax Cloud ({username})",
                        data=self._data,
                    )
        
        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_HUB_ID, default="ajax_hub"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional("try_anyway", default=False): BooleanSelector(),
                vol.Optional(CONF_USE_SIA, default=True): BooleanSelector(),
                vol.Optional(CONF_SIA_PORT, default=DEFAULT_SIA_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                ),
                vol.Optional(CONF_SIA_ACCOUNT, default="AAA"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }),
            errors=errors,
            description_placeholders={
                "api_note": "⚠️ WARNING: The Ajax Cloud API was CLOSED in 2018 and no longer works. Use SIA Protocol instead. The Enterprise API is only available to commercial partners.",
            },
        )
    
    async def async_step_jeedom(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure Jeedom Cloud Proxy."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            jeedom_username = user_input.get(CONF_JEEDOM_USERNAME, "")
            jeedom_password = user_input.get(CONF_JEEDOM_PASSWORD, "")
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
                    jeedom_username=jeedom_username,
                    jeedom_password=jeedom_password,
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
                    CONF_USE_CLOUD: False,
                    CONF_USE_MQTT: False,
                    CONF_USE_JEEDOM_PROXY: True,
                    CONF_JEEDOM_USERNAME: jeedom_username,
                    CONF_JEEDOM_PASSWORD: jeedom_password,
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
                
                await self.async_set_unique_id(f"ajax_jeedom_{ajax_username}")
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"Ajax via Jeedom ({ajax_username})",
                    data=self._data,
                )
        
        return self.async_show_form(
            step_id="jeedom",
            data_schema=vol.Schema({
                vol.Required(CONF_JEEDOM_USERNAME): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_JEEDOM_PASSWORD): TextSelector(
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
                "jeedom_note": "Requires a Jeedom Market account (market.jeedom.com). This uses the Jeedom cloud as a proxy to control your Ajax system.",
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
