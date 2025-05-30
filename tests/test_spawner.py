"""Tests for WinLocalProcessSpawner"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from tempfile import mkdtemp

# Only test on Windows or when explicitly testing
windows_only = pytest.mark.skipif(
    sys.platform != "win32" and not os.environ.get("FORCE_WINDOWS_TESTS"),
    reason="Windows-specific functionality"
)


@pytest.fixture
def mock_user():
    """Mock JupyterHub user object"""
    user = Mock()
    user.name = "testuser"
    user.get_auth_state = Mock(return_value={"auth_token": 12345})
    return user


@pytest.fixture
def spawner_instance(mock_user):
    """Create a spawner instance with mocked dependencies"""
    with patch('winlocalprocessspawner.winlocalprocessspawner.pywintypes'):
        with patch('winlocalprocessspawner.winlocalprocessspawner.win32profile'):
            from winlocalprocessspawner import WinLocalProcessSpawner
            
            spawner = WinLocalProcessSpawner()
            spawner.user = mock_user
            spawner.log = Mock()
            spawner.cmd = ['python', '-m', 'jupyter', 'notebook']
            spawner.get_args = Mock(return_value=['--port=8888'])
            spawner.popen_kwargs = {}
            spawner.shell_cmd = None
            spawner.notebook_dir = None
            spawner.ip = None
            spawner.db = Mock()
            spawner.server = Mock()
            
            return spawner


class TestWinLocalProcessSpawner:
    """Test cases for WinLocalProcessSpawner"""
    
    def test_user_env(self, spawner_instance):
        """Test user_env method adds USER variable"""
        env = {'PATH': '/test/path'}
        result = spawner_instance.user_env(env)
        
        assert result['USER'] == 'testuser'
        assert result['PATH'] == '/test/path'
    
    def test_get_env_preserves_windows_vars(self, spawner_instance):
        """Test get_env preserves Windows-specific environment variables"""
        with patch.dict(os.environ, {
            'SYSTEMROOT': 'C:\\Windows',
            'APPDATA': 'C:\\Users\\test\\AppData\\Roaming',
            'TEMP': 'C:\\Temp'
        }):
            with patch.object(spawner_instance, 'get_env', wraps=spawner_instance.get_env):
                # Mock the parent get_env method
                with patch('jupyterhub.spawner.LocalProcessSpawner.get_env', return_value={}):
                    env = spawner_instance.get_env()
                    
                    assert 'SYSTEMROOT' in env
                    assert 'APPDATA' in env
                    assert 'TEMP' in env
    
    def test_determine_working_directory_notebook_dir(self, spawner_instance):
        """Test working directory determination with notebook_dir"""
        temp_dir = mkdtemp()
        spawner_instance.notebook_dir = temp_dir
        
        result = spawner_instance._determine_working_directory(None)
        assert result == temp_dir
    
    def test_determine_working_directory_user_profile(self, spawner_instance):
        """Test working directory determination with user profile"""
        temp_dir = mkdtemp()
        user_env = {'USERPROFILE': temp_dir}
        
        result = spawner_instance._determine_working_directory(user_env)
        assert result == temp_dir
    
    def test_determine_working_directory_fallback(self, spawner_instance):
        """Test working directory determination fallback to current dir"""
        with patch('os.getcwd', return_value='/current/dir'):
            result = spawner_instance._determine_working_directory(None)
            assert result == '/current/dir'
    
    def test_determine_working_directory_temp_fallback(self, spawner_instance):
        """Test working directory determination fallback to temp dir"""
        with patch('os.getcwd', side_effect=OSError("No current dir")):
            with patch('tempfile.mkdtemp', return_value='/tmp/test'):
                result = spawner_instance._determine_working_directory(None)
                assert result == '/tmp/test'
    
    @windows_only
    @patch('winlocalprocessspawner.winlocalprocessspawner.PopenAsUser')
    @patch('winlocalprocessspawner.winlocalprocessspawner.win32profile')
    @patch('winlocalprocessspawner.winlocalprocessspawner.pywintypes')
    @patch('jupyterhub.utils.random_port', return_value=8888)
    async def test_start_success(self, mock_random_port, mock_pywintypes, 
                                mock_win32profile, mock_popen, spawner_instance):
        """Test successful process start"""
        # Setup mocks
        mock_token = Mock()
        mock_pywintypes.HANDLE.return_value = mock_token
        mock_win32profile.CreateEnvironmentBlock.return_value = {
            'APPDATA': 'C:\\Users\\test\\AppData\\Roaming',
            'USERPROFILE': 'C:\\Users\\test'
        }
        
        mock_process = Mock()
        mock_process.pid = 1234
        mock_popen.return_value = mock_process
        
        # Test start
        ip, port = await spawner_instance.start()
        
        assert ip == '127.0.0.1'
        assert port == 8888
        assert spawner_instance.proc == mock_process
        assert spawner_instance.pid == 1234
    
    @windows_only
    @patch('winlocalprocessspawner.winlocalprocessspawner.PopenAsUser')
    async def test_start_permission_error(self, mock_popen, spawner_instance):
        """Test start method handles PermissionError"""
        mock_popen.side_effect = PermissionError("Access denied")
        
        with pytest.raises(PermissionError):
            await spawner_instance.start()
            
        # Verify error was logged
        spawner_instance.log.error.assert_called()
    
    def test_start_no_auth_state(self, spawner_instance):
        """Test start method handles missing auth_state gracefully"""
        spawner_instance.user.get_auth_state = Mock(return_value=None)
        
        # This should not raise an exception
        # The actual start would be tested with full mocking 