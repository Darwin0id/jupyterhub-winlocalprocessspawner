import os
import ctypes
import logging
import sys
from subprocess import Popen, list2cmdline, Handle
from typing import Optional, Any, Union, List, Dict, IO

import win32process
import win32security
import win32service
import win32con
import win32api
import win32event

logger = logging.getLogger('winlocalprocessspawner')

DWORD = ctypes.c_uint
HANDLE = DWORD
BOOL = ctypes.wintypes.BOOL

CLOSEHANDLE = ctypes.windll.kernel32.CloseHandle
CLOSEHANDLE.argtypes = [HANDLE]
CLOSEHANDLE.restype = BOOL

GENERIC_ACCESS = (
    win32con.GENERIC_READ
    | win32con.GENERIC_WRITE
    | win32con.GENERIC_EXECUTE
    | win32con.GENERIC_ALL
)

WINSTA_ALL = (
    win32con.WINSTA_ACCESSCLIPBOARD
    | win32con.WINSTA_ACCESSGLOBALATOMS
    | win32con.WINSTA_CREATEDESKTOP
    | win32con.WINSTA_ENUMDESKTOPS
    | win32con.WINSTA_ENUMERATE
    | win32con.WINSTA_EXITWINDOWS
    | win32con.WINSTA_READATTRIBUTES
    | win32con.WINSTA_READSCREEN
    | win32con.WINSTA_WRITEATTRIBUTES
    | win32con.DELETE
    | win32con.READ_CONTROL
    | win32con.WRITE_DAC
    | win32con.WRITE_OWNER
)

DESKTOP_ALL = (
    win32con.DESKTOP_CREATEMENU
    | win32con.DESKTOP_CREATEWINDOW
    | win32con.DESKTOP_ENUMERATE
    | win32con.DESKTOP_HOOKCONTROL
    | win32con.DESKTOP_JOURNALPLAYBACK
    | win32con.DESKTOP_JOURNALRECORD
    | win32con.DESKTOP_READOBJECTS
    | win32con.DESKTOP_SWITCHDESKTOP
    | win32con.DESKTOP_WRITEOBJECTS
    | win32con.DELETE
    | win32con.READ_CONTROL
    | win32con.WRITE_DAC
    | win32con.WRITE_OWNER
)


def setup_sacl(user_group_sid: Any) -> None:
    """
    Set up Security Access Control List (SACL) for the given user SID.
    
    Without this setup, the single user server will likely fail with either 
    Error 0x0000142 or ExitCode -1073741502. This sets up access for the given 
    user to the WinSta (Window Station) and Desktop objects.
    
    Args:
        user_group_sid: Security identifier for the user group
        
    Raises:
        Exception: If unable to set up window station or desktop permissions
    """
    try:
        # Set access rights to window station
        h_win_sta = win32service.OpenWindowStation(
            "winsta0", False, 
            win32con.READ_CONTROL | win32con.WRITE_DAC
        )
        
        # Get security descriptor by winsta0-handle
        sec_desc_win_sta = win32security.GetUserObjectSecurity(
            h_win_sta,
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION
            | win32con.GROUP_SECURITY_INFORMATION
        )

        # Get DACL from security descriptor
        dacl_win_sta = sec_desc_win_sta.GetSecurityDescriptorDacl()
        if dacl_win_sta is None:
            # Create DACL if not existing
            dacl_win_sta = win32security.ACL()

        # Add ACEs to DACL for specific user group
        dacl_win_sta.AddAccessAllowedAce(win32security.ACL_REVISION_DS, GENERIC_ACCESS, user_group_sid)
        dacl_win_sta.AddAccessAllowedAce(win32security.ACL_REVISION_DS, WINSTA_ALL, user_group_sid)

        # Set modified DACL for winsta0
        win32security.SetSecurityInfo(
            h_win_sta, win32security.SE_WINDOW_OBJECT,
            win32security.DACL_SECURITY_INFORMATION, 
            None, None, dacl_win_sta, None
        )

        # Set access rights to desktop
        h_desktop = win32service.OpenDesktop(
            "default", 0, False, 
            win32con.READ_CONTROL
            | win32con.WRITE_DAC
            | win32con.DESKTOP_WRITEOBJECTS
            | win32con.DESKTOP_READOBJECTS
        )
        
        # Get security descriptor by desktop-handle
        sec_desc_desktop = win32security.GetUserObjectSecurity(
            h_desktop,
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION
            | win32con.GROUP_SECURITY_INFORMATION
        )

        # Get DACL from security descriptor
        dacl_desktop = sec_desc_desktop.GetSecurityDescriptorDacl()
        if dacl_desktop is None:
            # Create DACL if not existing
            dacl_desktop = win32security.ACL()

        # Add ACEs to DACL for specific user group
        dacl_desktop.AddAccessAllowedAce(win32security.ACL_REVISION_DS, GENERIC_ACCESS, user_group_sid)
        dacl_desktop.AddAccessAllowedAce(win32security.ACL_REVISION_DS, DESKTOP_ALL, user_group_sid)

        # Set modified DACL for desktop
        win32security.SetSecurityInfo(
            h_desktop, win32security.SE_WINDOW_OBJECT,
            win32security.DACL_SECURITY_INFORMATION, 
            None, None, dacl_desktop, None
        )
        
    except Exception as exc:
        logger.error("Failed to setup SACL for user SID %s: %s", user_group_sid, exc)
        raise


class PopenAsUser(Popen):
    """
    Popen implementation that launches new process using the Windows auth token provided.
    
    This is needed to be able to launch a process as another user while maintaining
    proper Windows security context and permissions.
    """

    def __init__(
        self, 
        args: Union[str, List[str]], 
        bufsize: int = -1, 
        executable: Optional[str] = None,
        stdin: Optional[Union[int, IO[Any]]] = None, 
        stdout: Optional[Union[int, IO[Any]]] = None, 
        stderr: Optional[Union[int, IO[Any]]] = None,
        shell: bool = False, 
        cwd: Optional[str] = None, 
        env: Optional[Dict[str, str]] = None, 
        universal_newlines: bool = False,
        startupinfo: Optional[Any] = None, 
        creationflags: int = 0, 
        *, 
        encoding: Optional[str] = None,
        errors: Optional[str] = None, 
        token: Optional[Any] = None
    ) -> None:
        """
        Create new PopenAsUser instance.
        
        Args:
            args: Command line arguments
            bufsize: Buffer size for subprocess communication
            executable: Executable path (optional)
            stdin: Standard input stream
            stdout: Standard output stream  
            stderr: Standard error stream
            shell: Whether to use shell for execution
            cwd: Current working directory
            env: Environment variables
            universal_newlines: Whether to use universal newlines
            startupinfo: Windows startup information
            creationflags: Process creation flags
            encoding: Text encoding for streams
            errors: Error handling mode for encoding
            token: Windows authentication token
        """
        self._token = token
        super().__init__(
            args, bufsize, executable,
            stdin, stdout, stderr, None, False,
            shell, cwd, env, universal_newlines,
            startupinfo, creationflags, False, False, (),
            encoding=encoding, errors=errors
        )

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:
        """Clean up resources when exiting context manager."""
        # Detach to avoid invalidating underlying winhandle
        if self._token:
            try:
                self._token.Detach()
            except Exception as exc:
                logger.warning("Failed to detach token in __exit__: %s", exc)
        super().__exit__(type, value, traceback)

    # Mainly adapted from subprocess._execute_child, with the main exception that this
    # function calls CreateProcessAsUser instead of CreateProcess
    if sys.version_info >= (3, 13):
        def _execute_child(self, args, executable, preexec_fn, close_fds,
                        pass_fds, cwd, env,
                        startupinfo, creationflags, shell,
                        p2cread, p2cwrite,
                        c2pread, c2pwrite,
                        errread, errwrite,
                        unused_restore_signals,
                        unused_gid, unused_gids, unused_uid, unused_umask,
                        unused_start_new_session, unused_process_group):
            """Execute child process for Python 3.13+"""
            self.do_execute_child(args, executable, preexec_fn, close_fds,
                             pass_fds, cwd, env,
                             startupinfo, creationflags, shell,
                             p2cread, p2cwrite,
                             c2pread, c2pwrite,
                             errread, errwrite)
    elif sys.version_info >= (3, 9):
        def _execute_child(self, args, executable, preexec_fn, close_fds,
                        pass_fds, cwd, env,
                        startupinfo, creationflags, shell,
                        p2cread, p2cwrite,
                        c2pread, c2pwrite,
                        errread, errwrite,
                        unused_restore_signals,
                        unused_gid, unused_gids, unused_uid, unused_umask,
                        unused_start_new_session):
            """Execute child process for Python 3.9-3.12"""
            self.do_execute_child(args, executable, preexec_fn, close_fds,
                             pass_fds, cwd, env,
                             startupinfo, creationflags, shell,
                             p2cread, p2cwrite,
                             c2pread, c2pwrite,
                             errread, errwrite)
    else:
        def _execute_child(self, args, executable, preexec_fn, close_fds,
                       pass_fds, cwd, env,
                       startupinfo, creationflags, shell,
                       p2cread, p2cwrite,
                       c2pread, c2pwrite,
                       errread, errwrite,
                       unused_restore_signals, unused_start_new_session):
            """Execute child process for Python < 3.9"""
            self.do_execute_child(args, executable, preexec_fn, close_fds,
                             pass_fds, cwd, env,
                             startupinfo, creationflags, shell,
                             p2cread, p2cwrite,
                             c2pread, c2pwrite,
                             errread, errwrite)

    def do_execute_child(
        self, 
        args: Union[str, List[str]], 
        executable: Optional[str], 
        preexec_fn: Any, 
        close_fds: bool,
        pass_fds: Any, 
        cwd: Optional[str], 
        env: Optional[Dict[str, str]],
        startupinfo: Any, 
        creationflags: int, 
        shell: bool,
        p2cread: Any, 
        p2cwrite: Any,
        c2pread: Any, 
        c2pwrite: Any,
        errread: Any, 
        errwrite: Any
    ) -> None:
        """
        Execute the child process using CreateProcessAsUser.
        
        This method is adapted from subprocess._execute_child but uses
        CreateProcessAsUser instead of CreateProcess to support running
        processes under different user contexts.
        """
        assert not pass_fds, "pass_fds not supported on Windows."

        if not isinstance(args, str):
            args = list2cmdline(args)

        # Process startup details
        if startupinfo is None:
            startupinfo = win32process.STARTUPINFO()
        if -1 not in (p2cread, c2pwrite, errwrite):
            startupinfo.dwFlags |= win32process.STARTF_USESTDHANDLES
            startupinfo.hStdInput = p2cread
            startupinfo.hStdOutput = c2pwrite
            startupinfo.hStdError = errwrite

        if shell:
            startupinfo.dwFlags |= win32process.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = win32process.SW_HIDE
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            args = '{} /c "{}"'.format(comspec, args)

        # Setup security access control list if we have a token
        if self._token:
            try:
                sid, _ = win32security.GetTokenInformation(self._token, win32security.TokenUser)
                setup_sacl(sid)
            except Exception as exc:
                logger.warning("Failed to setup SACL: %s", exc)

        # Start the process
        hp = None
        ht = None
        try:
            hp, ht, pid, tid = win32process.CreateProcessAsUser(
                self._token, 
                executable, 
                args,
                None,  # no special security
                None,  # no special security
                int(not close_fds),
                creationflags,
                env,
                os.fspath(cwd) if cwd is not None else None,
                startupinfo
            )

            # Check for errors immediately after process creation
            err = win32api.GetLastError()
            if err:
                logger.error(
                    "Error %r when calling CreateProcessAsUser executable %s args %s with token %r", 
                    err, executable, args, self._token
                )
            else:
                # Wait briefly and check if process started successfully
                wait_result = win32event.WaitForSingleObject(hp, 1000)  # Wait max 1 second
                if wait_result == win32event.WAIT_OBJECT_0:
                    # Process exited within 1 second, check exit code
                    exit_code = win32process.GetExitCodeProcess(hp)
                    if exit_code != win32con.STILL_ACTIVE:
                        logger.error(
                            "Process exited immediately with code %r when calling CreateProcessAsUser "
                            "executable %s args %s with token %r",
                            exit_code, executable, args, self._token
                        )

        except Exception as exc:
            logger.error("Exception in CreateProcessAsUser: %s", exc)
            raise
        finally:
            # Child is launched. Close the parent's copy of those pipe
            # handles that only the child should have open.
            self._close_pipe_handles(p2cread, c2pwrite, errwrite)

        try:
            # Retain the process handle, but close the thread handle
            self._child_created = True
            # Popen stores the win handle as an int, not as a PyHandle
            if hp:
                self._handle = Handle(hp.Detach())
                self.pid = pid
        finally:
            # Convert PyHANDLE to integer for ctypes and close thread handle
            if ht:
                CLOSEHANDLE(int(ht))

    def _close_pipe_handles(self, p2cread: Any, c2pwrite: Any, errwrite: Any) -> None:
        """
        Close pipe handles that should only be open in the child process.
        
        Args:
            p2cread: Parent to child read handle
            c2pwrite: Child to parent write handle  
            errwrite: Error write handle
        """
        handles_to_close = [
            (p2cread, "p2cread"),
            (c2pwrite, "c2pwrite"), 
            (errwrite, "errwrite")
        ]
        
        for handle, name in handles_to_close:
            if handle != -1:
                try:
                    handle.Close()
                except Exception as exc:
                    logger.warning("Failed to close %s handle: %s", name, exc)
                    
        # Close devnull if it exists
        if hasattr(self, '_devnull'):
            try:
                os.close(self._devnull)
            except Exception as exc:
                logger.warning("Failed to close devnull: %s", exc)
