"""
Application Wrapper Module

Provides sophisticated application execution with pre/post operations,
environment management, and comprehensive process control.

Can be used as a Python library or as a CLI tool:
    python -m gt.app.wrapper [command] [args...]
"""

from ._exceptions import (
    WrapperError,
    PreRunError,
    PostRunError,
    ExecutionError
)
from ._models import (
    ExecutionResult,
    WrapperConfig
)
from ._wrapper import (
    ApplicationWrapper,
    create_wrapper
)
from ._commands import (
    CommandDefinition,
    CommandRegistry,
    find_commands_file
)
from ._discovery import (
    PackageInfo,
    get_packages,
    discover_packages_auto,
    load_packages_from_config
)
from ._cli import main as cli_main


__all__ = [
    # Core classes
    'ApplicationWrapper',
    'WrapperConfig',
    'ExecutionResult',
    
    # Exceptions
    'WrapperError',
    'PreRunError',
    'PostRunError',
    'ExecutionError',
    
    # Utility functions
    'create_wrapper',
    
    # CLI components
    'CommandDefinition',
    'CommandRegistry',
    'find_commands_file',
    'cli_main',
    
    # Package discovery
    'PackageInfo',
    'get_packages',
    'discover_packages_auto',
    'load_packages_from_config',
]
