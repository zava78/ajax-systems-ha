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

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AjaxDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
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
    
    # Register update listener for config changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
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
