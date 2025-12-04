"""Pytest fixtures for Ajax Systems tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "use_sia": True,
        "use_mqtt": False,
        "hub_id": "test_hub",
        "sia_port": 2410,
        "sia_account": "AAA",
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_jeedom_proxy():
    """Create a mock Jeedom Proxy API."""
    with patch("custom_components.ajax_systems.api.JeedomAjaxProxy") as mock:
        api = AsyncMock()
        api.authenticate = AsyncMock(return_value=True)
        api.get_hubs = AsyncMock(return_value=[])
        api.get_devices = AsyncMock(return_value=[])
        api.arm = AsyncMock(return_value=True)
        api.disarm = AsyncMock(return_value=True)
        api.night_mode = AsyncMock(return_value=True)
        api.close = AsyncMock()
        mock.return_value = api
        yield api


@pytest.fixture
def mock_sia_receiver():
    """Create a mock SIA receiver."""
    with patch("custom_components.ajax_systems.sia.SiaReceiver") as mock:
        receiver = AsyncMock()
        receiver.start = AsyncMock(return_value=True)
        receiver.stop = AsyncMock()
        mock.return_value = receiver
        yield receiver
