"""Command-line interface for envoy."""

import sys
import argparse
import logging
import shutil
from pathlib import Path

from ._commands import CommandRegistry, find_commands_file
from ._discovery import get_packages, PackageInfo
from ._environment import EnvironmentManager
from ._executor import ProcessExecutor
from ._wrapper import ApplicationWrapper
from ._models import WrapperConfig, ExecutionResult
from ._exceptions import WrapperError


log = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration.
    
    Args:
        verbose: Enable verbose logging
        
    """
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def list_commands(registry: CommandRegistry) -> int:
    """List all available commands.
    
    Args:
        registry: Command registry
        
    Returns:
        Exit code (0 for success)
        
    """
    commands = registry.list_commands()
    
    if not commands:
        print("No commands defined.")
        return 1
    
    print("Available commands:")
    print()
    
    for cmd_name in commands:
        cmd = registry.get(cmd_name)
        if cmd:
            # Build command display
            pkg_str = f" [{cmd.package}]" if cmd.package else ""
            
            if cmd.alias:
                alias_str = " ".join(cmd.alias)
                print(f"  {cmd_name:<20} → {alias_str}{pkg_str}")
            else:
                print(f"  {cmd_name:<20} (executable on PATH){pkg_str}")
    
    return 0


def show_command_info(registry: CommandRegistry, command_name: str) -> int:
    """Show detailed information about a command.
    
    Args:
        registry: Command registry
        command_name: Name of command to show
        
    Returns:
        Exit code (0 for success)
        
    """
    cmd = registry.get(command_name)
    
    if not cmd:
        print(f"Error: Command '{command_name}' not found")
        return 1
    
    print(f"Command: {command_name}")
    
    if cmd.package:
        print(f"Package: {cmd.package}")
    
    print(f"Executable: {cmd.executable}")
    
    if cmd.base_args:
        print(f"Base args: {' '.join(cmd.base_args)}")
    
    print(f"Environment files:")
    for env_file in cmd.environment:
        print(f"  - {env_file}")
    
    if cmd.envoy_env_dir:
        print(f"Environment directory: {cmd.envoy_env_dir}")
    
    if cmd.alias:
        print(f"Alias: {' '.join(cmd.alias)}")
    
    return 0


def show_which(registry: CommandRegistry, command_name: str) -> int:
    """Show the resolved executable path for a command.
    
    Args:
        registry: Command registry
        command_name: Name of command to find
        
    Returns:
        Exit code (0 for success)
        
    """
    cmd = registry.get(command_name)
    
    if not cmd:
        print(f"Error: Command '{command_name}' not found", file=sys.stderr)
        return 1
    
    # Try to resolve the executable path
    executable = cmd.executable
    resolved_path = None
    
    # Check if it's an absolute path that exists
    exe_path = Path(executable)
    if exe_path.is_absolute() and exe_path.exists():
        resolved_path = str(exe_path)
    else:
        # Try to find it on PATH
        resolved_path = shutil.which(executable)
    
    # Build the output message
    if cmd.alias:
        # Command has an alias
        alias_str = " ".join(cmd.alias)
        print(f"command {command_name} aliased to: {alias_str}")
    else:
        # Command uses its name as executable
        if resolved_path:
            print(f"command {command_name} resolved to: {resolved_path}")
        else:
            print(f"command {command_name} executable: {executable} (not found on PATH)")
    
    return 0


def run_command(
    registry: CommandRegistry,
    command_name: str,
    args: list[str],
    packages: list[PackageInfo] | None = None,
    verbose: bool = False
) -> int:
    """Run a command from the registry.
    
    Args:
        registry: Command registry
        command_name: Name of command to run
        args: Arguments to pass to the command
        packages: List of discovered packages (for multi-package env file search)
        verbose: Enable verbose output
        
    Returns:
        Exit code from the executed command
        
    """
    cmd = registry.get(command_name)
    
    if not cmd:
        print(f"Error: Command '{command_name}' not found", file=sys.stderr)
        print(f"Run 'envoy --list' to see available commands", file=sys.stderr)
        return 1
    
    # Collect environment files
    env_files = []
    
    if packages:
        # Multi-package mode: search for each env file across ALL packages
        for env_file_name in cmd.environment:
            for package in packages:
                env_file_path = package.envoy_env / env_file_name
                if env_file_path.exists():
                    env_files.append(str(env_file_path))
                    log.debug(f"Found environment file: {env_file_path}")
    else:
        # Legacy mode: use command's envoy_env_dir
        if cmd.envoy_env_dir:
            wrapper_env_dir = cmd.envoy_env_dir
        else:
            # Fall back to finding commands.json
            commands_file = find_commands_file()
            if commands_file:
                wrapper_env_dir = commands_file.parent
            else:
                print(f"Error: Cannot determine envoy_env directory", file=sys.stderr)
                return 1
        
        # Build full environment file paths
        env_files = [str(wrapper_env_dir / env_file) for env_file in cmd.environment]
        
        # Verify all environment files exist (only in legacy mode)
        for env_file in env_files:
            if not Path(env_file).exists():
                print(f"Error: Environment file not found: {env_file}", file=sys.stderr)
                return 1
    
    # Combine base args with user args
    full_args = cmd.base_args + args
    
    # Create wrapper config
    config = WrapperConfig(
        executable=cmd.executable,
        args=full_args,
        env_files=[Path(f) for f in env_files],
        capture_output=False,
        stream_output=True,
        log_execution=verbose
    )
    
    try:
        wrapper = ApplicationWrapper(config)
        result = wrapper.run()
        return result.return_code
        
    except WrapperError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 130


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code
        
    """
    parser = argparse.ArgumentParser(
        prog='envoy',
        description='Envoy: Environment orchestration for applications'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available commands'
    )
    
    parser.add_argument(
        '--info',
        metavar='COMMAND',
        help='Show detailed information about a command'
    )
    
    parser.add_argument(
        '--which',
        metavar='COMMAND',
        help='Show the resolved executable path for a command'
    )
    
    parser.add_argument(
        '--commands-file',
        type=Path,
        help='Path to commands.json file (auto-detected if not specified)'
    )
    
    parser.add_argument(
        '--packages-config',
        type=Path,
        help='Path to packages config file (auto-discovers from ENVOY_PKG_ROOTS if not specified)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        help='Command to execute'
    )
    
    parser.add_argument(
        'args',
        nargs='*',
        help='Arguments to pass to the command'
    )
    
    # Parse args - use parse_known_args to allow passthrough to commands
    if argv is None:
        argv = sys.argv[1:]
    
    args, unknown_args = parser.parse_known_args(argv)
    
    # Combine args with any unknown args (these should be passed to the command)
    if unknown_args:
        args.args = list(args.args) + unknown_args
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Initialize command registry
    registry = CommandRegistry()
    packages = None  # Track discovered packages for env file resolution
    
    # Determine command loading strategy
    if args.packages_config:
        # Load from packages config file
        try:
            discovered_packages = get_packages(config_file=args.packages_config)
            if discovered_packages:
                log.info(f"Discovered {len(discovered_packages)} package(s) from config file")
                registry.load_from_packages(discovered_packages)
                packages = discovered_packages
            else:
                log.warning("No packages found in config file")
        except WrapperError as e:
            print(f"Error loading packages config: {e}", file=sys.stderr)
            return 1
    elif args.commands_file:
        # Load from specific commands file (legacy mode)
        if not args.commands_file.exists():
            print(f"Error: Commands file not found: {args.commands_file}", file=sys.stderr)
            return 1
        try:
            registry.load_from_file(args.commands_file)
        except WrapperError as e:
            print(f"Error loading commands: {e}", file=sys.stderr)
            return 1
    else:
        # Try package auto-discovery first
        try:
            discovered_packages = get_packages()
            if discovered_packages:
                log.info(f"Auto-discovered {len(discovered_packages)} package(s)")
                registry.load_from_packages(discovered_packages)
                packages = discovered_packages
        except WrapperError as e:
            log.debug(f"Package auto-discovery failed: {e}")
        
        # Fall back to local commands.json if no packages found
        if len(registry) == 0:
            commands_file = find_commands_file()
            if commands_file:
                try:
                    registry.load_from_file(commands_file)
                except WrapperError as e:
                    print(f"Error loading commands: {e}", file=sys.stderr)
                    return 1
            else:
                print("Error: Could not find commands.json", file=sys.stderr)
                print("Searched for envoy_env/commands.json in current directory and parents", file=sys.stderr)
                print("Or set ENVOY_PKG_ROOTS environment variable for auto-discovery", file=sys.stderr)
                return 1
    
    # Check if we have any commands
    if len(registry) == 0:
        print("Error: No commands loaded", file=sys.stderr)
        return 1
    
    # Handle list commands
    if args.list:
        return list_commands(registry)
    
    # Handle command info
    if args.info:
        return show_command_info(registry, args.info)
    
    # Handle which
    if args.which:
        return show_which(registry, args.which)
    
    # Must have a command to execute
    if not args.command:
        parser.print_help()
        return 0
    
    # Execute command
    return run_command(
        registry=registry,
        command_name=args.command,
        args=args.args,
        packages=packages,
        verbose=args.verbose
    )


if __name__ == '__main__':
    sys.exit(main())
