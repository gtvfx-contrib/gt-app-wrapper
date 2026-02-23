"""
envoy -- Environment orchestration for managed application execution.

Provides environment isolation, bundle-based discovery, and process launch
facilities for DCC applications and pipeline tools.

Can be used as a Python library or as a CLI tool::

    python -m gt.envoy [command] [args...]

Quickstart (Python API)::

    import gt.envoy as envoy
    import gt.envoy.proc as proc

    # Inspect the prepared environment for a command
    env_dict = envoy.get_environment('maya')

    # Launch once
    proc.call(['maya', 'myfile.ma'])

    # Bake env once, launch many
    env = proc.Environment('nuke')
    env.spawn(['comp.nk'])

    # Inspect an individual bundle (analogous to bl.Package)
    bundle = envoy.Bundle('gt:pythoncore')           # resolve by bndlid via ENVOY_BNDL_ROOTS
    bundle = envoy.Bundle('/repo/gtvfx-contrib/gt/pythoncore')  # or by path
    print(bundle.bndlid)    # 'gt:pythoncore'  (namespace inferred from parent dir)
    print(bundle.name)      # 'pythoncore'
    print(bundle.namespace) # 'gt'
    print(bundle.commands)

    # Load a bundle config file (analogous to bl.Pipeline)
    cfg = envoy.BundleConfig('/studio/bundles.json')
    for b in cfg.bundles:
        print(b.name, b.commands)

Submodules:
    proc       -- process execution (Environment class and free functions)
    testing    -- test helpers (patch_bundle_roots, patch_commands_file)
    exceptions -- all gt.envoy exception classes
"""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

#: The version of gt.envoy.
__version__: str = '0.1.0'

from ._exceptions import (
    EnvoyError,
    WrapperError,
    PreRunError,
    PostRunError,
    ExecutionError,
    EnvironmentBuildError,
    CommandNotFoundError,
    CalledProcessError,
    ValidationError,
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
    BundleInfo,
    Bundle,
    BundleConfig,
    BUNDLE_CHECKOUT,
    BUNDLE_DEFAULT_NAMESPACE,
    get_bundles,
    discover_bundles_auto,
    load_bundles_from_config
)
from ._environment import _CORE_ENV_VARS, _ENVOY_ENV_VARS
from ._cli import main as cli_main

# Convenience submodule imports — ``import gt.envoy`` makes these available as
# ``gt.envoy.proc``, ``gt.envoy.testing``, and ``gt.envoy.exceptions``.
# This module eagerly imports these submodules at import time.
from . import proc       # noqa: E402
from . import testing    # noqa: E402
from . import exceptions # noqa: E402


def set_api_verbosity(level: int | str) -> None:
    """Set the logging verbosity for the ``gt.envoy`` logger.

    Analogous to ``bl.setAPIVerbosity()``.  Pass a :mod:`logging` level
    constant (``logging.DEBUG``, ``logging.INFO``, etc.) or its string
    equivalent (``'DEBUG'``, ``'INFO'``, etc.).

    Args:
        level: New log level for the ``gt.envoy`` logger tree.

    Example::

        import logging
        import gt.envoy as envoy

        envoy.set_api_verbosity(logging.DEBUG)
    """
    logging.getLogger('gt.envoy').setLevel(level)


# ---------------------------------------------------------------------------
# Public constants (mirrors bl.OPERATING_SYSTEM / bl.SUPPORTED_OPERATING_SYSTEMS)
# ---------------------------------------------------------------------------

#: The current operating system name as returned by :func:`platform.system`
#: (e.g. ``'Windows'``, ``'Linux'``, ``'Darwin'``).
OPERATING_SYSTEM: str = platform.system()

#: Operating systems that envoy officially supports.
SUPPORTED_OPERATING_SYSTEMS: tuple[str, ...] = ('Windows', 'Linux', 'Darwin')


# ---------------------------------------------------------------------------
# Public Command class
# ---------------------------------------------------------------------------

#: Public alias for :class:`~._commands.CommandDefinition`.
#:
#: Exposes ``.name``, ``.alias``, ``.bundle``, ``.environment``,
#: ``.executable``, and ``.base_args`` — a superset of ``bl.Command``.
Command = CommandDefinition


# ---------------------------------------------------------------------------
# Top-level API functions
# ---------------------------------------------------------------------------

def get_environment(
    command: str,
    *,
    inherit_env: bool = False,
    allowlist: list[str] | None = None,
    bundle_roots: list[str] | None = None,
    commands_file: Path | None = None,
) -> dict[str, str]:
    """Build and return the subprocess environment dict for *command*.

    This is a convenience wrapper around :class:`~.proc.Environment` that
    constructs and returns the environment dictionary without launching any
    process.  Useful for debugging, inspection, or passing to other tools.

    Args:
        command: The envoy command name (e.g. ``'maya'``).
        inherit_env: When ``True`` the returned dict is based on the full
            current process environment.  When ``False`` (default) only env
            file variables and the built-in OS seed vars are included.
        allowlist: Additional system variable names to include in closed mode.
        bundle_roots: Override bundle discovery roots.
        commands_file: Explicit ``commands.json`` path.

    Returns:
        The fully expanded subprocess environment dictionary.

    Raises:
        ~.CommandNotFoundError: If *command* is not registered.
        ~.EnvironmentBuildError: If environment preparation fails.

    Example::

        env = envoy.get_environment('maya')
        print(env.get('MAYA_VERSION'))
    """
    return proc.Environment(
        command,
        inherit_env=inherit_env,
        allowlist=allowlist,
        bundle_roots=bundle_roots,
        commands_file=commands_file,
    ).build()


def get_allowlist(extra: list[str] | None = None) -> frozenset[str]:
    """Return the default set of system variable names that envoy seeds in
    closed mode.

    This is the union of :data:`~._environment._CORE_ENV_VARS` (identity,
    temp, system paths, locale) and :data:`~._environment._ENVOY_ENV_VARS`
    (``ENVOY_BNDL_ROOTS``, ``ENVOY_ALLOWLIST``).

    Mirrors ``bl.getPlatformEnvironmentAllowlist()``.

    Args:
        extra: Additional variable names to include in the returned set.

    Returns:
        The combined allowlist as a :class:`frozenset`.

    Example::

        # See what's always seeded on this platform
        for var in sorted(envoy.get_allowlist()):
            print(var)
    """
    base = _CORE_ENV_VARS | _ENVOY_ENV_VARS
    if extra:
        return base | frozenset(extra)
    return base


__all__ = [
    # ---- Public constants ----
    '__version__',
    'OPERATING_SYSTEM',
    'SUPPORTED_OPERATING_SYSTEMS',
    'BUNDLE_CHECKOUT',

    # ---- Core classes ----
    'ApplicationWrapper',
    'WrapperConfig',
    'ExecutionResult',
    'Command',
    'CommandDefinition',
    'CommandRegistry',
    'Bundle',
    'BundleConfig',
    'BundleInfo',

    # ---- Exceptions ----
    'EnvoyError',
    'WrapperError',
    'PreRunError',
    'PostRunError',
    'ExecutionError',
    'EnvironmentBuildError',
    'CommandNotFoundError',
    'CalledProcessError',
    'ValidationError',

    # ---- Top-level API functions ----
    'get_environment',
    'get_allowlist',
    'set_api_verbosity',

    # ---- Utility functions ----
    'create_wrapper',
    'find_commands_file',
    'cli_main',

    # ---- Bundle discovery ----
    'get_bundles',
    'discover_bundles_auto',
    'load_bundles_from_config',

    # ---- Submodules ----
    'proc',
    'testing',
    'exceptions',
]

