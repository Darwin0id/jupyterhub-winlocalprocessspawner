import os
import sys
import shlex
import shutil
from tempfile import mkdtemp
from typing import Dict, Any, Optional, Tuple, List, Union

from jupyterhub.spawner import LocalProcessSpawner
from jupyterhub.utils import random_port
from traitlets import log

import pywintypes
import win32profile

from .win_utils import PopenAsUser


class WinLocalProcessSpawner(LocalProcessSpawner):
    """
    A Spawner that starts single-user servers as local Windows processes.

    This spawner uses Windows authentication tokens stored in the 'auth_token' field 
    of the current auth_state. The Authenticator is responsible for providing a valid 
    Windows authentication token handle in the auth_state.

    Features:
    - Launches processes with user-specific environment variables
    - Sets appropriate working directory based on user profile
    - Handles Windows-specific security considerations
    - Provides fallback mechanisms for missing user profiles
    """

    def user_env(self, env: Dict[str, str]) -> Dict[str, str]:
        """
        Augment environment of spawned process with user specific env variables.
        
        Args:
            env: Base environment dictionary to augment
            
        Returns:
            Environment dictionary with user-specific variables added
        """
        env['USER'] = self.user.name
        return env

    def get_env(self) -> Dict[str, str]:
        """
        Get the complete set of environment variables to be set in the spawned process.
        
        Returns:
            Dictionary of environment variables for the spawned process
        """
        # Windows-specific environment variables that should be preserved
        win_env_keep = ['SYSTEMROOT', 'APPDATA', 'WINDIR', 'USERPROFILE', 'TEMP']

        env = super().get_env()
        
        # Preserve critical Windows environment variables
        for key in win_env_keep:
            if key in os.environ:
                env[key] = os.environ[key]
                
        return env

    async def start(self) -> Tuple[str, int]:
        """
        Start the single-user server.
        
        Returns:
            Tuple of (ip, port) where the server is listening
            
        Raises:
            PermissionError: If insufficient permissions to start process
            Exception: For other startup failures
        """
        self.port = random_port()
        cmd: List[str] = []
        env = self.get_env()
        token: Optional[pywintypes.HANDLEType] = None

        cmd.extend(self.cmd)
        cmd.extend(self.get_args())

        if self.shell_cmd:
            # using shell_cmd (e.g. bash -c),
            # add our cmd list as the last (single) argument:
            cmd = self.shell_cmd + [' '.join(shlex.quote(s) for s in cmd)]

        self.log.info("Spawning %s", ' '.join(shlex.quote(s) for s in cmd))

        # Get authentication token from auth_state
        auth_state = await self.user.get_auth_state()
        if auth_state:
            token_value = auth_state.get('auth_token')
            if token_value:
                try:
                    token = pywintypes.HANDLE(token_value)
                except Exception as exc:
                    self.log.warning("Failed to create token handle for %s: %s", 
                                   self.user.name, exc)

        user_env: Optional[Dict[str, str]] = None
        cwd: Optional[str] = None

        # Load user environment if token is available
        if token:
            try:
                # Will load user variables, if the user profile is loaded
                user_env = win32profile.CreateEnvironmentBlock(token, False)
                env.update(user_env)
                
                # Validate APPDATA exists and is writable
                if 'APPDATA' not in user_env or not user_env['APPDATA']:
                    self.log.warning("APPDATA not found in user environment for %s, "
                                   "using PUBLIC directory", self.user.name)
                    if 'PUBLIC' in user_env:
                        user_env['USERPROFILE'] = user_env['PUBLIC']
                    
            except Exception as exc:
                self.log.warning("Failed to load user environment for %s: %s", 
                               self.user.name, exc)

        # Set working directory
        cwd = self._determine_working_directory(user_env)

        popen_kwargs = dict(
            token=token,
            cwd=cwd,
        )

        popen_kwargs.update(self.popen_kwargs)
        # don't let user config override env
        popen_kwargs['env'] = env
        
        try:
            self.proc = PopenAsUser(cmd, **popen_kwargs)
            self.pid = self.proc.pid
            
        except PermissionError:
            # use which to get abspath
            script = shutil.which(cmd[0]) or cmd[0]
            self.log.error("Permission denied trying to run %r. Does %s have access to this file?",
                           script, self.user.name)
            raise
        except Exception as exc:
            self.log.error("Failed to start process for %s: %s", self.user.name, exc)
            raise
        finally:
            # Always clean up token handle
            if token:
                try:
                    token.Detach()
                except Exception as exc:
                    self.log.warning("Failed to detach token for %s: %s", 
                                   self.user.name, exc)

        # Handle compatibility with different JupyterHub versions
        if self.__class__ is not LocalProcessSpawner:
            # subclasses may not pass through return value of super().start,
            # relying on deprecated 0.6 way of setting ip, port,
            # so keep a redundant copy here for now.
            # A deprecation warning will be shown if the subclass
            # does not return ip, port.
            if self.ip:
                self.server.ip = self.ip
            self.server.port = self.port
            self.db.commit()

        return (self.ip or '127.0.0.1', self.port)

    def _determine_working_directory(self, user_env: Optional[Dict[str, str]]) -> str:
        """
        Determine the appropriate working directory for the spawned process.
        
        Args:
            user_env: User environment variables dictionary, may be None
            
        Returns:
            Path to use as working directory
        """
        # Priority order for working directory:
        # 1. notebook_dir if configured
        # 2. User's USERPROFILE if available
        # 3. Current working directory as fallback
        # 4. Temporary directory as last resort
        
        if self.notebook_dir:
            if os.path.isdir(self.notebook_dir):
                return self.notebook_dir
            else:
                self.log.warning("Configured notebook_dir %s does not exist, using fallback", 
                               self.notebook_dir)
        
        if user_env and user_env.get('USERPROFILE'):
            userprofile = user_env['USERPROFILE']
            if os.path.isdir(userprofile):
                return userprofile
                
        # Try current working directory
        try:
            cwd = os.getcwd()
            return cwd
        except Exception as exc:
            self.log.warning("Failed to get current working directory: %s", exc)
            
        # Last resort: create a temporary directory
        temp_dir = mkdtemp()
        self.log.warning("Using temporary directory as working directory: %s", temp_dir)
        return temp_dir
