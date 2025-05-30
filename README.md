# WinLocalProcessSpawner
WinLocalProcessSpawner spawns single-user servers as local Windows processes. It uses the authentication credentials stored in the **auth_token** field of [auth_state](http://jupyterhub.readthedocs.io/en/latest/reference/authenticators.html). It is the Authenticator's responsibility to store the Windows authentication token in the **auth_token**. If JupyterHub was launched with "Local System" privileges, the **auth_token** will have a user profile associated with it, which will allow the spawner to extract the per-user APPDATA and USERPROFILE environment variables. Those variables are used to set the jupyter runtime directory and the CWD respectively.

For an example of this architecture, check the [WinAuthenticator](https://github.com/ni/jupyterhub-winauthenticator).

## Installation

### From Source
Currently, there is no PyPI package, so you need to install winlocalprocessspawner by cloning the repo:

```bash
git clone https://github.com/Darwin0id/jupyterhub-winlocalprocessspawner.git
cd jupyterhub-winlocalprocessspawner
pip install -e .
```

## Usage
To enable, add the following to your JupyterHub configuration file:

```python
c.JupyterHub.spawner_class = 'winlocalprocessspawner.WinLocalProcessSpawner'
```

## Requirements
- Windows operating system
- JupyterHub >= 1.0.0
- pywin32 >= 227
- Python >= 3.7 (including Python 3.13)

**Python Version Support:**
- Python 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13
- Tested and compatible with the latest Python releases

## Development
To set up for development:

```bash
git clone https://github.com/Darwin0id/jupyterhub-winlocalprocessspawner.git
cd jupyterhub-winlocalprocessspawner
pip install -e .[dev]
```

### Python 3.13 Compatibility
This package fully supports Python 3.13 with:
- Updated subprocess handling for Python 3.13+ 
- Enhanced type hints compatible with latest Python features
- Modernized development tooling (Black, mypy, flake8)
- Comprehensive test suite that works across all Python versions

### Testing
Run tests with:
```bash
pytest
```

For Python 3.13 specific testing:
```bash
python3.13 -m pytest
```