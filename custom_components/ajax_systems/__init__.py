"""The Ajax Systems integration for Home Assistant.

Custom integration for Ajax Systems security alarms.

CREDITS & RESOURCES:
====================
GitHub Repository: https://github.com/zava78/ajax-systems-ha
Author: @zava78

Based on:
- ajax-systems-api by Igor Mukhin: https://github.com/igormukhingmailcom/ajax-systems-api
- Jeedom Ajax plugin by Flobul: https://github.com/Flobul/Jeedom-ajax
- pysiaalarm by E. van Valkenburg: https://github.com/eavanvalkenburg/pysiaalarm

Official Resources:
- Ajax Systems: https://ajax.systems/
- Ajax Enterprise API: https://ajax.systems/blog/enterprise-api/

DISCLAIMER:
This is an UNOFFICIAL integration. Ajax Systems does not provide a public API.
Use at your own risk.
"""
from __future__ import annotations

import logging
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .coordinator import AjaxDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ajax Systems from a config entry."""
    _LOGGER.debug("Setting up Ajax Systems integration")
    
    coordinator = AjaxDataCoordinator(hass, entry)
    
    # Set up coordinator
    if not await coordinator.async_setup():
        _LOGGER.error("Failed to set up Ajax Systems coordinator")
        return False
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up MQTT publisher after entities are created
    await coordinator.async_setup_mqtt_publisher()
    
    # Register update listener for config changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    # Register diagnostic service
    async def handle_diagnose(call: ServiceCall) -> None:
        """Handle diagnose API service call."""
        _LOGGER.info("Running Ajax API diagnostics...")
        
        for coord in hass.data[DOMAIN].values():
            if hasattr(coord, 'cloud_api') and coord.cloud_api:
                try:
                    results = await coord.cloud_api.diagnose_api()
                    _LOGGER.info("=== AJAX API DIAGNOSTICS ===")
                    _LOGGER.info("Authenticated: %s", results.get("authenticated"))
                    _LOGGER.info("Session ID: %s", results.get("session_id"))
                    
                    for endpoint, data in results.get("endpoints_tested", {}).items():
                        _LOGGER.info("--- Endpoint: %s ---", endpoint)
                        for key, value in data.items():
                            _LOGGER.info("  %s: %s", key, value)
                    
                    # Also log to persistent notification
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "Ajax API Diagnostics",
                            "message": f"Check Home Assistant logs for full diagnostics.\n\nAuthenticated: {results.get('authenticated')}\nEndpoints tested: {len(results.get('endpoints_tested', {}))}",
                            "notification_id": "ajax_diagnostics",
                        }
                    )
                except Exception as e:
                    _LOGGER.error("Diagnostics failed: %s", e)
    
    hass.services.async_register(DOMAIN, "diagnose_api", handle_diagnose)
    
    # Register Jeedom refresh service
    async def handle_refresh_jeedom(call: ServiceCall) -> None:
        """Handle refresh Jeedom devices service call."""
        _LOGGER.info("Requesting Jeedom to refresh all Ajax device states...")
        
        for coord in hass.data[DOMAIN].values():
            if hasattr(coord, 'async_request_jeedom_refresh'):
                try:
                    await coord.async_request_jeedom_refresh()
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "Ajax Systems",
                            "message": "Requested Jeedom to refresh all Ajax device states. Check logs for updates.",
                            "notification_id": "ajax_jeedom_refresh",
                        }
                    )
                except Exception as e:
                    _LOGGER.error("Jeedom refresh failed: %s", e)
    
    hass.services.async_register(DOMAIN, "refresh_jeedom", handle_refresh_jeedom)
    
    _LOGGER.info("Ajax Systems integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Ajax Systems integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Shut down coordinator
        coordinator: AjaxDataCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()
        
        # Remove data
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
