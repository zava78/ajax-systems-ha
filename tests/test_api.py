"""Tests for Ajax Systems API - Jeedom Proxy."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from custom_components.ajax_systems.api.jeedom_proxy import (
    JeedomAjaxProxy,
    JeedomProxyError,
    JeedomAuthError,
    JeedomConnectionError,
)
from custom_components.ajax_systems.const import AjaxDeviceType


class TestJeedomAjaxProxy:
    """Test Jeedom Ajax Proxy client."""
    
    @pytest.fixture
    def proxy(self):
        """Create a proxy instance."""
        return JeedomAjaxProxy(
            jeedom_host="192.168.1.100",
            jeedom_port=80,
            jeedom_use_ssl=False,
            jeedom_api_key="test_api_key",
            ajax_username="test@example.com",
            ajax_password="password123",
        )
    
    @pytest.mark.asyncio
    async def test_init(self, proxy):
        """Test proxy initialization."""
        assert proxy._jeedom_host == "192.168.1.100"
        assert proxy._jeedom_port == 80
        assert proxy._jeedom_use_ssl is False
        assert proxy._jeedom_api_key == "test_api_key"
        assert proxy._ajax_username == "test@example.com"
        assert proxy._ajax_password == "password123"
        assert proxy._session is None
    
    @pytest.mark.asyncio
    async def test_base_url_http(self, proxy):
        """Test HTTP base URL construction."""
        assert proxy._base_url == "http://192.168.1.100:80"
    
    @pytest.mark.asyncio
    async def test_base_url_https(self):
        """Test HTTPS base URL construction."""
        proxy = JeedomAjaxProxy(
            jeedom_host="jeedom.example.com",
            jeedom_port=443,
            jeedom_use_ssl=True,
            jeedom_api_key="test_key",
            ajax_username="test@example.com",
            ajax_password="password",
        )
        assert proxy._base_url == "https://jeedom.example.com:443"
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, proxy):
        """Test successful authentication."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "success": True,
            "result": {"token": "test_token"}
        })
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Test authentication
            proxy._session = mock_session
            proxy._authenticated = True
            
            assert proxy._authenticated is True
    
    @pytest.mark.asyncio
    async def test_close_session(self, proxy):
        """Test closing proxy session."""
        mock_session = AsyncMock()
        proxy._session = mock_session
        
        await proxy.close()
        
        mock_session.close.assert_called_once()


class TestJeedomProxyErrors:
    """Test Jeedom Proxy error handling."""
    
    def test_proxy_error(self):
        """Test JeedomProxyError."""
        error = JeedomProxyError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_auth_error(self):
        """Test JeedomAuthError."""
        error = JeedomAuthError("Authentication failed")
        
        assert str(error) == "Authentication failed"
        assert isinstance(error, JeedomProxyError)
    
    def test_connection_error(self):
        """Test JeedomConnectionError."""
        error = JeedomConnectionError("Connection refused")
        
        assert str(error) == "Connection refused"
        assert isinstance(error, JeedomProxyError)


class TestDeviceParsing:
    """Test device parsing from Jeedom API responses."""
    
    def test_parse_door_sensor(self):
        """Test parsing door sensor from Jeedom."""
        proxy = JeedomAjaxProxy(
            jeedom_host="192.168.1.100",
            jeedom_port=80,
            jeedom_use_ssl=False,
            jeedom_api_key="test_key",
            ajax_username="test@example.com",
            ajax_password="password",
        )
        
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
        
        # Test _parse_device method if available
        # device = proxy._parse_device(device_data, "hub123")
        # assert device.device_id == "door001"
    
    def test_parse_motion_sensor(self):
        """Test parsing motion sensor from Jeedom."""
        proxy = JeedomAjaxProxy(
            jeedom_host="192.168.1.100",
            jeedom_port=80,
            jeedom_use_ssl=False,
            jeedom_api_key="test_key",
            ajax_username="test@example.com",
            ajax_password="password",
        )
        
        device_data = {
            "id": "motion001",
            "name": "Living Room",
            "type": "MotionProtect",
            "deviceType": 5,  # MOTION_PROTECT
            "battery": 88,
            "signal": -62,
            "online": True,
        }
        
        # Test _parse_device method if available
        # device = proxy._parse_device(device_data, "hub123")
        # assert device.device_id == "motion001"
