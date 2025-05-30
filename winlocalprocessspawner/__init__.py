"""Windows local process Jupyterhub spawner

A spawner for JupyterHub that launches single-user servers as local Windows processes
using Windows authentication tokens.
"""

__version__ = "1.0.0"

from winlocalprocessspawner.winlocalprocessspawner import WinLocalProcessSpawner

__all__ = ['WinLocalProcessSpawner', '__version__']
