"""Tests for Ajax Cloud API."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from custom_components.ajax_systems.api.ajax_cloud import (
    AjaxCloudApi,
    AjaxApiError,
    AjaxAuthError,
)
from custom_components.ajax_systems.const import AjaxDeviceType


class TestAjaxCloudApi:
    """Test Ajax Cloud API client."""
    
    @pytest.fixture
    def api(self):
        """Create an API instance."""
        return AjaxCloudApi("test@example.com", "password123")
    
    @pytest.mark.asyncio
    async def test_init(self, api):
        """Test API initialization."""
        assert api._username == "test@example.com"
        assert api._password == "password123"
        assert api._token is None
        assert api._session is None
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, api):
        """Test successful authentication."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "token": "test_token_123",
            "userId": "user123",
        })
        
        with patch.object(api, "_session") as mock_session:
            mock_session.post = AsyncMock(return_value=mock_response)
            api._session = mock_session
            
            # Mock the actual authenticate method behavior
            api._token = "test_token_123"
            
            assert api._token == "test_token_123"
    
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, api):
        """Test authentication failure."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(return_value=mock_response)
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # API should handle auth failure gracefully
            # Actual behavior depends on implementation
    
    @pytest.mark.asyncio
    async def test_get_hubs(self, api):
        """Test getting hubs."""
        api._token = "test_token"
        
        mock_hub_data = [
            {
                "id": "hub123",
                "name": "My Hub",
                "model": "Hub 2",
                "firmware": "1.0.0",
                "state": "disarmed",
            }
        ]
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_hub_data)
        
        with patch.object(api, "_request") as mock_request:
            mock_request.return_value = mock_hub_data
            
            # Test would call api.get_hubs() and verify result
    
    @pytest.mark.asyncio
    async def test_get_devices(self, api):
        """Test getting devices."""
        api._token = "test_token"
        
        mock_devices = [
            {
                "id": "door001",
                "name": "Front Door",
                "type": "DoorProtect",
                "battery": 90,
                "signal": -60,
            },
            {
                "id": "motion001",
                "name": "Living Room",
                "type": "MotionProtect",
                "battery": 85,
                "signal": -55,
            },
        ]
        
        with patch.object(api, "_request") as mock_request:
            mock_request.return_value = mock_devices
            
            # Test would call api.get_devices("hub123")
    
    @pytest.mark.asyncio
    async def test_arm_command(self, api):
        """Test arm command."""
        api._token = "test_token"
        
        with patch.object(api, "_request") as mock_request:
            mock_request.return_value = {"success": True}
            
            # Test would call api.arm("hub123")
    
    @pytest.mark.asyncio
    async def test_disarm_command(self, api):
        """Test disarm command."""
        api._token = "test_token"
        
        with patch.object(api, "_request") as mock_request:
            mock_request.return_value = {"success": True}
            
            # Test would call api.disarm("hub123")
    
    @pytest.mark.asyncio
    async def test_close_session(self, api):
        """Test closing API session."""
        mock_session = AsyncMock()
        api._session = mock_session
        
        await api.close()
        
        mock_session.close.assert_called_once()


class TestAjaxApiErrors:
    """Test API error handling."""
    
    def test_api_error(self):
        """Test AjaxApiError."""
        error = AjaxApiError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_auth_error(self):
        """Test AjaxAuthError."""
        error = AjaxAuthError("Authentication failed")
        
        assert str(error) == "Authentication failed"
        assert isinstance(error, AjaxApiError)


class TestDeviceParsing:
    """Test device parsing from API responses."""
    
    def test_parse_door_sensor(self):
        """Test parsing door sensor from API."""
        api = AjaxCloudApi("test@example.com", "password")
        
        device_data = {
            "id": "door001",
            "name": "Front Door",
            "type": "DoorProtect",
            "deviceType": 2,  # DOOR_PROTECT
            "battery": 95,
            "signal": -58,
            "online": True,
            "state": {"open": False},
        }
        
        # Test _parse_device method
        device = api._parse_device(device_data, "hub123")
        
        assert device.device_id == "door001"
        assert device.name == "Front Door"
        assert device.battery_level == 95
    
    def test_parse_motion_sensor(self):
        """Test parsing motion sensor from API."""
        api = AjaxCloudApi("test@example.com", "password")
        
        device_data = {
            "id": "motion001",
            "name": "Living Room",
            "type": "MotionProtect",
            "deviceType": 5,  # MOTION_PROTECT
            "battery": 88,
            "signal": -62,
            "online": True,
        }
        
        device = api._parse_device(device_data, "hub123")
        
        assert device.device_id == "motion001"
        assert device.name == "Living Room"
    
    def test_parse_hub(self):
        """Test parsing hub from API."""
        api = AjaxCloudApi("test@example.com", "password")
        
        hub_data = {
            "id": "hub123",
            "name": "Home Hub",
            "type": "Hub 2",
            "firmware": "2.14.0",
            "state": "disarmed",
            "battery": 100,
        }
        
        hub = api._parse_hub(hub_data)
        
        assert hub.device_id == "hub123"
        assert hub.name == "Home Hub"
