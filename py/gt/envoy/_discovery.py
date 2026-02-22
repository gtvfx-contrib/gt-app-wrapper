"""Bundle discovery for wrapper environments.

Supports two methods of discovering bundles:
1. Auto-discovery: Search directories specified in ENVOY_BNDL_ROOTS for git repositories
2. Config file: Explicit list of bundle paths

"""

import os
import logging
from pathlib import Path
import json

from ._exceptions import WrapperError


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version sentinel constants  (analogous to bl.Package version strings)
# ---------------------------------------------------------------------------

#: Version sentinel for a bundle that lives directly in a git checkout.
#: Analogous to ``bl.Package(version='checkout')``.
#: All :class:`Bundle` objects constructed from a filesystem path use this
#: version until the versioned-build system is implemented.
BUNDLE_CHECKOUT: str = 'checkout'


class BundleInfo:
    """Information about a discovered bundle."""
    
    def __init__(self, root: Path, name: str):
        """Initialize bundle information.
        
        Args:
            root: Root directory of the bundle
            name: Name of the bundle (directory name)
        
        """
        self.root = root
        self.name = name
        self.envoy_env = root / "envoy_env"
        self.env_files: dict[str, Path] = self._index_env_files()

    def _index_env_files(self) -> dict[str, Path]:
        """Scan envoy_env/ once and index all JSON files by filename.
        
        Returns:
            Dict mapping filename to absolute Path
        
        """
        if not self.envoy_env.is_dir():
            return {}
        return {f.name: f for f in self.envoy_env.glob('*.json')}
        
    def __repr__(self):
        return f"BundleInfo(name={self.name}, root={self.root})"
    
    def __str__(self):
        return f"{self.name} ({self.root})"


# ---------------------------------------------------------------------------
# Public API classes  (analogous to bl.Package and bl.Pipeline)
# ---------------------------------------------------------------------------

class Bundle:
    """A discovered envoy bundle.

    Analogous to ``bl.Package``.  A bundle is a directory (or, in the future,
    a versioned built directory) that contains an ``envoy_env/`` subdirectory
    with a ``commands.json`` and one or more environment JSON files.

    **Current behaviour (checkout mode)**

    All bundles are constructed from a filesystem path that points directly to
    a live git repository on disk.  :attr:`version` always returns
    :data:`BUNDLE_CHECKOUT` and :attr:`is_production` is always ``False``.

    **Planned versioned behaviour (future)**

    Bundles will also be constructable by *name* + *version* once the
    build/publish pipeline is in place::

        # Checkout (current — path to a git repo):
        bundle = Bundle('/repo/gtvfx-contrib/gt/pythoncore')
        assert bundle.version == 'checkout'
        assert bundle.is_checkout is True

        # Production — future, resolved from the built-bundle registry:
        bundle = Bundle('pythoncore', version='1.2.3')   # not yet implemented
        bundle = Bundle('pythoncore', version='latest')  # not yet implemented
        assert bundle.is_production is True

    A production bundle is the result of ``git tag`` → build-to-directory
    process, analogous to how ``bl`` publishes packages.  The
    :class:`BundleConfig` file will pin these versions (see its docstring
    for the planned config format).

    Args:
        path: Root directory of the bundle (required for checkout mode).

    Raises:
        ValueError: If *path* does not exist or lacks an ``envoy_env/``
            subdirectory.

    Example::

        bundle = Bundle('/repo/gtvfx-contrib/gt/pythoncore')
        print(bundle.name)         # 'pythoncore'
        print(bundle.version)      # 'checkout'
        print(bundle.is_checkout)  # True
        print(bundle.commands)     # ['python_dev', ...]
    """

    def __init__(self, path: str | Path) -> None:
        root = Path(path).resolve()
        if not root.is_dir():
            raise ValueError(f"Bundle path does not exist: {root}")
        if not (root / 'envoy_env').is_dir():
            raise ValueError(f"Not a valid bundle (no envoy_env/): {root}")
        self._info = BundleInfo(root=root, name=root.name)

    @classmethod
    def _from_info(cls, info: 'BundleInfo') -> 'Bundle':
        """Construct from an internal :class:`BundleInfo` (no re-validation)."""
        obj = object.__new__(cls)
        obj._info = info
        return obj

    @property
    def name(self) -> str:
        """The bundle directory name."""
        return self._info.name

    @property
    def version(self) -> str:
        """Version string for this bundle.

        Currently always :data:`BUNDLE_CHECKOUT` (``'checkout'``), indicating
        the bundle is a live git-repository checkout rather than a built and
        published release directory.

        When the versioned-build system is implemented this property will
        return a semantic-version string (e.g. ``'1.2.3'``) for production
        bundles, mirroring ``bl.Package.version``.
        """
        return BUNDLE_CHECKOUT

    @property
    def is_production(self) -> bool:
        """``True`` if this bundle is a built, versioned release directory.

        Always ``False`` in the current implementation — all bundles are git
        checkout directories.  Mirrors ``bl.Package.isProduction``.

        When the versioned-build pipeline is available, production bundles
        will be resolved from a central registry and this property will
        return ``True``.
        """
        return False

    @property
    def is_checkout(self) -> bool:
        """``True`` if this bundle is a live git-repository checkout.

        This is the inverse of :attr:`is_production` and always ``True``
        in the current implementation.
        """
        return not self.is_production

    @property
    def path(self) -> Path:
        """Absolute path to the bundle root directory."""
        return self._info.root

    @property
    def envoy_env(self) -> Path:
        """Absolute path to the ``envoy_env/`` subdirectory."""
        return self._info.envoy_env

    @property
    def env_files(self) -> dict[str, Path]:
        """Mapping of JSON filename → absolute path for all env files."""
        return dict(self._info.env_files)

    @property
    def commands(self) -> list[str]:
        """Sorted list of command names defined in this bundle's ``commands.json``.

        Returns an empty list if the file is absent or cannot be parsed.
        """
        commands_file = self._info.envoy_env / 'commands.json'
        if not commands_file.exists():
            return []
        try:
            with commands_file.open() as fh:
                data = json.load(fh)
            return sorted(data.keys()) if isinstance(data, dict) else []
        except (json.JSONDecodeError, OSError):
            return []

    def __repr__(self) -> str:
        return f"Bundle(name={self.name!r}, path={self.path})"

    def __str__(self) -> str:
        return repr(self)


class BundleConfig:
    """An envoy bundle configuration file.

    Analogous to ``bl.Pipeline``.  A bundle config is a JSON file that
    declares which bundles envoy should use — the file passed to the CLI
    via ``--bundles-config``/``-bc``.

    **Current format** — flat list of filesystem paths (all checkout mode)::

        ["R:/repo/gtvfx-contrib/gt/pythoncore",
         "R:/repo/gtvfx-contrib/gt/globals"]

        or {"bundles": ["...", "..."]}

    **Planned versioned format** (future — once the build/publish pipeline
    exists)::

        {
            "bundles": {
                "pythoncore": "1.2.3",
                "globals": "latest",
                "my_local_tool": "checkout:/path/to/local"
            }
        }

    In the versioned model each bundle entry resolves to a built output
    directory tagged with the requested version, analogous to how a
    ``bl`` pipeline pins specific ``bl.Package`` versions.  The
    ``checkout:`` prefix will preserve the current path-based behaviour
    for in-development bundles, mirroring ``bl.Package(version='checkout')``.

    Args:
        path: Path to the bundle config JSON file.

    Raises:
        ValueError: If *path* does not exist.

    Example::

        cfg = BundleConfig('/studio/envoy_bundles.json')
        for bundle in cfg.bundles:
            print(bundle.name, bundle.version, bundle.is_checkout)
        print(cfg.commands)   # merged command list across all bundles
    """

    def __init__(self, path: str | Path) -> None:
        p = Path(path).resolve()
        if not p.is_file():
            raise ValueError(f"BundleConfig path does not exist: {p}")
        self._path = p
        self._bundles: list[Bundle] | None = None

    @property
    def path(self) -> Path:
        """Absolute path to the config file."""
        return self._path

    @property
    def bundles(self) -> list[Bundle]:
        """List of :class:`Bundle` objects declared in this config.

        Loaded and cached on first access.
        """
        if self._bundles is None:
            infos = load_bundles_from_config(self._path)
            self._bundles = [Bundle._from_info(info) for info in infos]
        return self._bundles

    @property
    def commands(self) -> list[str]:
        """Sorted list of all command names across all bundles (deduplicated)."""
        seen: set[str] = set()
        for bundle in self.bundles:
            seen.update(bundle.commands)
        return sorted(seen)

    def __repr__(self) -> str:
        return f"BundleConfig(path={self._path})"

    def __str__(self) -> str:
        return repr(self)


def is_git_repo(path: Path) -> bool:
    """Check if a directory is a git repository.
    
    Args:
        path: Path to check
        
    Returns:
        True if path contains a .git directory
    
    """
    return (path / ".git").is_dir()


def has_envoy_env(path: Path) -> bool:
    """Check if a directory has an envoy_env subdirectory.
    
    Args:
        path: Path to check
        
    Returns:
        True if path contains an envoy_env directory
    
    """
    return (path / "envoy_env").is_dir()


def validate_bundle(path: Path) -> bool:
    """Validate that a path is a valid envoy bundle.
    
    A valid bundle must:
    - Be a directory
    - Have an envoy_env subdirectory
    
    Args:
        path: Path to validate
        
    Returns:
        True if path is a valid bundle
    
    """
    if not path.is_dir():
        return False
    
    if not has_envoy_env(path):
        return False
    
    return True


def find_git_repos(root_dir: Path, max_depth: int = 5) -> list[Path]:
    """Recursively find git repositories under a root directory.
    
    Args:
        root_dir: Root directory to search
        max_depth: Maximum depth to search
        
    Returns:
        List of paths to git repository roots
    
    """
    repos = []
    
    if not root_dir.is_dir():
        logger.warning(f"Root directory does not exist: {root_dir}")
        return repos
    
    def search_dir(path: Path, depth: int = 0):
        """Recursively search for git repos.
        
        """
        if depth > max_depth:
            return
        
        try:
            # Check if this directory is a git repo
            if is_git_repo(path):
                repos.append(path)
                # Don't search inside git repos
                return
            
            # Search subdirectories
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    search_dir(item, depth + 1)
        except PermissionError:
            logger.debug(f"Permission denied: {path}")
        except Exception as e:
            logger.debug(f"Error searching {path}: {e}")
    
    search_dir(root_dir)
    return repos


def discover_bundles_from_roots(root_dirs: list[str]) -> list[BundleInfo]:
    """Discover bundles in specified root directories.
    
    Searches for git repositories and validates them as envoy bundles.
    
    Args:
        root_dirs: List of root directory paths
        
    Returns:
        List of discovered bundles
    
    """
    bundles = []
    
    for root_str in root_dirs:
        root = Path(root_str).resolve()
        logger.debug(f"Searching for bundles in: {root}")
        
        # Find all git repos under this root
        git_repos = find_git_repos(root)
        logger.debug(f"Found {len(git_repos)} git repositories in {root}")
        
        # Validate each repo as a bundle
        for repo_path in git_repos:
            if validate_bundle(repo_path):
                bundle = BundleInfo(
                    root=repo_path,
                    name=repo_path.name
                )
                bundles.append(bundle)
                logger.info(f"Discovered bundle: {bundle}")
            else:
                logger.debug(f"Git repo is not an envoy bundle: {repo_path}")
    
    return bundles


def discover_bundles_auto() -> list[BundleInfo]:
    """Auto-discover bundles using ENVOY_BNDL_ROOTS environment variable.
    
    ENVOY_BNDL_ROOTS should contain a list of root directories separated by
    the OS path separator (';' on Windows, ':' on Unix).
    
    Returns:
        List of discovered bundles
    
    """
    roots_str = os.environ.get('ENVOY_BNDL_ROOTS', '')
    
    if not roots_str:
        logger.debug("ENVOY_BNDL_ROOTS not set, no auto-discovery")
        return []
    
    # Split by OS path separator
    separator = ';' if os.name == 'nt' else ':'
    root_dirs = [r.strip() for r in roots_str.split(separator) if r.strip()]
    
    if not root_dirs:
        logger.debug("ENVOY_BNDL_ROOTS is empty")
        return []
    
    logger.info(f"Auto-discovering bundles from {len(root_dirs)} root(s)")
    return discover_bundles_from_roots(root_dirs)


def load_bundles_from_config(config_file: Path) -> list[BundleInfo]:
    """Load bundle paths from a configuration file.
    
    Config file format (JSON):
    {
        "bundles": [
            "/path/to/package1",
            "/path/to/package2"
        ]
    }
    
    or (JSON array):
    [
        "/path/to/package1",
        "/path/to/package2"
    ]
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        List of bundles from config file
        
    Raises:
        WrapperError: If config file is invalid
    
    """
    if not config_file.is_file():
        raise WrapperError(f"Config file not found: {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise WrapperError(f"Invalid JSON in config file: {e}")
    except Exception as e:
        raise WrapperError(f"Error reading config file: {e}")
    
    # Support both {"bundles": [...]} and direct array [...]
    if isinstance(data, dict):
        bundle_paths = data.get('bundles', [])
    elif isinstance(data, list):
        bundle_paths = data
    else:
        raise WrapperError("Config file must be a JSON object or array")
    
    bundles = []
    for path_str in bundle_paths:
        path = Path(path_str).resolve()
        
        if not validate_bundle(path):
            logger.warning(f"Invalid bundle in config: {path}")
            continue
        
        bundle = BundleInfo(
            root=path,
            name=path.name
        )
        bundles.append(bundle)
        logger.info(f"Loaded bundle from config: {bundle}")
    
    return bundles


def get_bundles(config_file: Path | None = None) -> list[BundleInfo]:
    """Get all bundles using config file or auto-discovery.
    
    If config_file is provided, only bundles from the config are used.
    Otherwise, auto-discovery is attempted using ENVOY_BNDL_ROOTS.
    
    Args:
        config_file: Optional path to config file
        
    Returns:
        List of discovered bundles
    
    """
    if config_file:
        logger.info(f"Using bundle config file: {config_file}")
        return load_bundles_from_config(config_file)
    else:
        logger.debug("No config file, attempting auto-discovery")
        return discover_bundles_auto()


def get_bundle_env_files(bundles: list[BundleInfo]) -> dict[str, list[Path]]:
    """Get all environment files from discovered bundles.
    
    Returns a mapping of bundle names to their environment JSON files.
    
    Args:
        bundles: List of bundles to scan
    
    Returns:
        Dict mapping bundle name to list of environment file paths
    
    """
    env_files = {}
    
    for bundle in bundles:
        files = []
        wrapper_env = bundle.envoy_env
        
        if wrapper_env.is_dir():
            # Find all .json files in envoy_env
            for json_file in wrapper_env.glob("*.json"):
                # Skip commands.json as it's handled separately
                if json_file.name != "commands.json":
                    files.append(json_file)
        
        if files:
            env_files[bundle.name] = files
            logger.debug(f"Bundle {bundle.name}: {len(files)} environment file(s)")
    
    return env_files


def get_bundle_commands_files(bundles: list[BundleInfo]) -> dict[str, Path]:
    """Get commands.json files from discovered bundles.
    
    Returns a mapping of bundle names to their commands.json files.
    
    Args:
        bundles: List of bundles to scan
    
    Returns:
        Dict mapping bundle name to commands.json path
    
    """
    commands_files = {}
    
    for bundle in bundles:
        commands_file = bundle.envoy_env / "commands.json"
        
        if commands_file.is_file():
            commands_files[bundle.name] = commands_file
            logger.debug(f"Bundle {bundle.name}: has commands.json")
    
    return commands_files
