import os
from setuptools import setup, find_packages

# Read version from __init__.py
def get_version():
    init_file = os.path.join(os.path.dirname(__file__), 'winlocalprocessspawner', '__init__.py')
    with open(init_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('\'"')
    return '1.0.0'

# Read README for long description
def get_long_description():
    readme_file = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_file):
        with open(readme_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ''

setup(
    name='jupyterhub-winlocalprocessspawner',
    version=get_version(),
    description='Windows Local Process Spawner for JupyterHub',
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/Darwin0id/jupyterhub-winlocalprocessspawner',
    author='Alejandro del Castillo',
    author_email='',
    license='MIT',
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=[
        'pywin32>=227',
        'jupyterhub>=1.0.0',
    ],
    extras_require={
        'dev': [
            'pytest>=6.0',
            'pytest-asyncio>=0.18.0',
            'black>=22.0',
            'flake8>=4.0',
            'mypy>=0.991',
            'isort>=5.10',
        ],
        'test': [
            'pytest>=6.0',
            'pytest-asyncio>=0.18.0',
            'pytest-cov>=3.0',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Systems Administration',
        'Framework :: Jupyter',
        'Framework :: Jupyter :: JupyterHub',
    ],
    keywords='jupyterhub spawner windows authentication process',
    project_urls={
        'Bug Reports': 'https://github.com/Darwin0id/jupyterhub-winlocalprocessspawner/issues',
        'Source': 'https://github.com/Darwin0id/jupyterhub-winlocalprocessspawner',
        'Documentation': 'https://github.com/Darwin0id/jupyterhub-winlocalprocessspawner#readme',
    },
    zip_safe=False,
)
