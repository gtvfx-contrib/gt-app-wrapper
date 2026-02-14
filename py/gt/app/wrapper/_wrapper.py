"""Core application wrapper implementation."""

import os
import sys
import subprocess
import logging
import signal
import time
import shutil
import json
import re
from pathlib import Path
from typing import Any, Callable
from contextlib import contextmanager

from ._exceptions import WrapperError, PreRunError, PostRunError, ExecutionError
from ._models import ExecutionResult, WrapperConfig


log = logging.getLogger(__name__)


class ApplicationWrapper:
    """Sophisticated application wrapper with pre/post operations and process control.
    
    Example:
        >>> config = WrapperConfig(
        ...     executable="python",
        ...     args=["script.py", "--verbose"],
        ...     pre_run=lambda: print("Starting..."),
        ...     post_run=lambda result: print(f"Done: {result}")
        ... )
        >>> wrapper = ApplicationWrapper(config)
        >>> result = wrapper.run()
        >>> print(result.return_code)
        
    """
    
    def __init__(self, config: WrapperConfig):
        """Initialize the application wrapper.
        
        Args:
            config: WrapperConfig instance with execution settings
            
        """
        self.config = config
        self._process: subprocess.Popen | None = None
        self._interrupted = False
        self._original_sigint_handler = None
        
        # Setup logging
        if config.log_execution:
            self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging for wrapper execution.
        
        """
        if not log.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            log.addHandler(handler)
        log.setLevel(self.config.log_level)
    
    def _resolve_executable(self) -> str:
        """Resolve executable path, checking PATH if necessary.
        
        Returns:
            Absolute path to executable
            
        Raises:
            WrapperError: If executable cannot be found
            
        """
        exe = str(self.config.executable)
        
        # If it's an absolute path or relative path with directory separators
        if os.path.isabs(exe) or os.path.dirname(exe):
            if not os.path.exists(exe):
                raise WrapperError(f"Executable not found: {exe}")
            return os.path.abspath(exe)
        
        # Search in PATH
        found = shutil.which(exe)
        if found:
            return found
        
        raise WrapperError(f"Executable '{exe}' not found in PATH")
    
    def _expand_env_value(self, value: str, current_env: dict[str, str]) -> str:
        """Expand environment variable references in a value string.
        
        Supports {$VARNAME} syntax to reference existing environment variables.
        Looks up variables in current_env first, then os.environ.
        
        Args:
            value: String potentially containing {$VARNAME} references
            current_env: Current environment dictionary being built
            
        Returns:
            Expanded string value
            
        """
        # Pattern to match {$VARNAME}
        pattern = re.compile(r'\{\$([A-Za-z_][A-Za-z0-9_]*)\}')
        
        def replacer(match):
            var_name = match.group(1)
            # Check current_env first, then os.environ
            if var_name in current_env:
                return current_env[var_name]
            return os.environ.get(var_name, '')
        
        return pattern.sub(replacer, value)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize Unix-style paths to OS-specific format.
        
        Converts forward slashes to backslashes on Windows.
        Leaves paths unchanged on Unix systems.
        
        Args:
            path: Path string (can use Unix-style forward slashes)
            
        Returns:
            Normalized path for the current OS
            
        """
        if os.name == 'nt':
            # On Windows, convert forward slashes to backslashes
            return path.replace('/', '\\')
        return path
    
    def _process_env_value(self, value: Any, merged_env: dict[str, str]) -> str:
        """Process an environment variable value from JSON.
        
        Handles:
        - Lists: joined with OS path separator
        - Strings: used as-is
        - Other types: converted to string
        - {$VARNAME} expansion
        - Path normalization (Unix to Windows if needed)
        
        Args:
            value: The value from JSON (string, list, or other)
            merged_env: Current environment dictionary for variable expansion
            
        Returns:
            Processed string value
            
        """
        # Determine path separator based on OS
        path_sep = ';' if os.name == 'nt' else ':'
        
        # Handle list values - join with path separator
        if isinstance(value, list):
            # Normalize each path in the list
            normalized_paths = [self._normalize_path(str(item)) for item in value]
            str_value = path_sep.join(normalized_paths)
        else:
            # Convert to string and normalize
            str_value = self._normalize_path(str(value))
        
        # Expand any {$VARNAME} references
        expanded_value = self._expand_env_value(str_value, merged_env)
        
        return expanded_value
    
    def _load_env_from_files(self) -> dict[str, str]:
        """Load environment variables from JSON file(s).
        
        Files are merged in order, with later files overriding earlier ones.
        Supports variable expansion, append/prepend operators, and path lists.
        
        Examples in JSON:
            List:     "PYTHONPATH": ["R:/path1", "R:/path2", "R:/path3"]
            Append:   "+=PYTHONPATH": ["R:/new/path"]
            Prepend:  "^=PYTHONPATH": "R:/new/path"
            Replace:  "PYTHONPATH": "R:/new/path"
            Variable: "PYTHONPATH": "{$PYTHONPATH};R:/new/path"
        
        Paths can use Unix-style forward slashes, automatically converted on Windows.
        
        Returns:
            Dictionary of environment variables from files
            
        Raises:
            WrapperError: If file cannot be read or parsed
            
        """
        if not self.config.env_files:
            return {}
        
        # Normalize to list
        env_files = self.config.env_files
        if isinstance(env_files, (str, Path)):
            env_files = [env_files]
        
        # Determine path separator based on OS
        path_sep = ';' if os.name == 'nt' else ':'
        
        merged_env = {}
        
        for file_path in env_files:
            path = Path(file_path)
            
            if not path.exists():
                raise WrapperError(f"Environment file not found: {path}")
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    file_env = json.load(f)
                
                if not isinstance(file_env, dict):
                    raise WrapperError(
                        f"Environment file must contain a JSON object: {path}"
                    )
                
                # Process each key-value pair
                for key, value in file_env.items():
                    # Check for operators
                    append_mode = False
                    prepend_mode = False
                    var_name = key
                    
                    if key.startswith('+='):
                        append_mode = True
                        var_name = key[2:]  # Remove += prefix
                    elif key.startswith('^='):
                        prepend_mode = True
                        var_name = key[2:]  # Remove ^= prefix
                    
                    # Process the value (handles lists, normalization, expansion)
                    processed_value = self._process_env_value(value, merged_env)
                    
                    # Handle append/prepend operations
                    if append_mode or prepend_mode:
                        # Get current value from merged_env or os.environ
                        current_value = merged_env.get(var_name) or os.environ.get(var_name, '')
                        
                        if append_mode:
                            # Append: current + separator + new
                            if current_value:
                                merged_env[var_name] = f"{current_value}{path_sep}{processed_value}"
                            else:
                                merged_env[var_name] = processed_value
                        else:  # prepend_mode
                            # Prepend: new + separator + current
                            if current_value:
                                merged_env[var_name] = f"{processed_value}{path_sep}{current_value}"
                            else:
                                merged_env[var_name] = processed_value
                    else:
                        # Normal assignment - just set the value
                        merged_env[var_name] = processed_value
                
                log.info(f"Loaded {len(file_env)} environment variables from {path}")
                
            except json.JSONDecodeError as e:
                raise WrapperError(f"Invalid JSON in environment file {path}: {e}") from e
            except Exception as e:
                raise WrapperError(f"Error reading environment file {path}: {e}") from e
        
        return merged_env
    
    def _prepare_environment(self) -> dict[str, str]:
        """Prepare environment variables for subprocess.
        
        Priority (later overrides earlier):
        1. System environment (if inherit_env=True)
        2. Environment from JSON files (env_files)
        3. Explicit environment dict (env)
        
        Returns:
            Dictionary of environment variables
            
        """
        if self.config.inherit_env:
            env = os.environ.copy()
        else:
            env = {}
        
        # Load from files (overrides inherited env)
        file_env = self._load_env_from_files()
        env.update(file_env)
        
        # Explicit env dict overrides everything
        if self.config.env:
            env.update(self.config.env)
        
        return env
    
    def _prepare_command(self) -> list[str]:
        """Prepare the full command to execute.
        
        Returns:
            List of command components
            
        """
        exe = self._resolve_executable()
        return [exe] + list(self.config.args)
    
    def _handle_signal(self, signum, frame):
        """Handle interrupt signals.
        
        """
        log.warning(f"Received signal {signum}, terminating process...")
        self._interrupted = True
        if self._process:
            self._terminate_process()
    
    def _terminate_process(self):
        """Terminate the running process gracefully.
        
        """
        if not self._process:
            return
        
        try:
            # Try graceful termination first
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if termination takes too long
                log.warning("Process did not terminate gracefully, forcing kill...")
                self._process.kill()
                self._process.wait()
        except Exception as e:
            log.error(f"Error terminating process: {e}")
    
    @contextmanager
    def _signal_handler_context(self):
        """Context manager for signal handling.
        
        """
        self._original_sigint_handler = signal.signal(signal.SIGINT, self._handle_signal)
        try:
            yield
        finally:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
    
    def _execute_pre_run(self):
        """Execute pre-run operations.
        
        """
        if not self.config.pre_run:
            return
        
        try:
            log.info("Executing pre-run operations...")
            self.config.pre_run()
            log.info("Pre-run operations completed")
        except Exception as e:
            log.error(f"Pre-run operation failed: {e}")
            if not self.config.continue_on_pre_run_error:
                raise PreRunError(f"Pre-run operation failed: {e}") from e
    
    def _execute_post_run(self, result: ExecutionResult):
        """Execute post-run operations.
        
        """
        if not self.config.post_run:
            return
        
        try:
            log.info("Executing post-run operations...")
            self.config.post_run(result)
            log.info("Post-run operations completed")
        except Exception as e:
            log.error(f"Post-run operation failed: {e}")
            if not self.config.continue_on_post_run_error:
                raise PostRunError(f"Post-run operation failed: {e}") from e
    
    def _stream_output(self, process: subprocess.Popen) -> tuple[str, str]:
        """Stream output from process in real-time.
        
        Args:
            process: Running subprocess
            
        Returns:
            Tuple of (stdout, stderr) as strings
            
        """
        stdout_lines = []
        stderr_lines = []
        
        # Read stdout
        if process.stdout:
            for line in iter(process.stdout.readline, b''):
                if not line:
                    break
                decoded = line.decode('utf-8', errors='replace').rstrip()
                stdout_lines.append(decoded)
                
                if self.config.stream_output:
                    print(decoded, file=sys.stdout, flush=True)
                
                if self.config.on_output:
                    try:
                        self.config.on_output(decoded)
                    except Exception as e:
                        log.warning(f"on_output callback error: {e}")
        
        # Read stderr
        if process.stderr:
            for line in iter(process.stderr.readline, b''):
                if not line:
                    break
                decoded = line.decode('utf-8', errors='replace').rstrip()
                stderr_lines.append(decoded)
                
                if self.config.stream_output:
                    print(decoded, file=sys.stderr, flush=True)
                
                if self.config.on_error:
                    try:
                        self.config.on_error(decoded)
                    except Exception as e:
                        log.warning(f"on_error callback error: {e}")
        
        return '\n'.join(stdout_lines), '\n'.join(stderr_lines)
    
    def run(self) -> ExecutionResult:
        """Execute the application with configured settings.
        
        Returns:
            ExecutionResult with execution details
            
        Raises:
            WrapperError: On execution failures (if raise_on_error=True)
            
        """
        start_time = time.time()
        result = ExecutionResult(
            return_code=-1,
            command=[]
        )
        
        try:
            # Pre-run operations
            self._execute_pre_run()
            
            # Prepare execution
            command = self._prepare_command()
            env = self._prepare_environment()
            cwd = str(self.config.cwd) if self.config.cwd else None
            
            result.command = command
            
            log.info(f"Executing: {' '.join(command)}")
            if cwd:
                log.info(f"Working directory: {cwd}")
            
            # Setup process arguments
            process_kwargs = {
                'env': env,
                'cwd': cwd,
                'shell': self.config.shell,
            }
            
            if self.config.capture_output or self.config.stream_output:
                process_kwargs['stdout'] = subprocess.PIPE
                process_kwargs['stderr'] = subprocess.PIPE
            
            # Execute with signal handling
            with self._signal_handler_context():
                self._process = subprocess.Popen(command, **process_kwargs)
                result.pid = self._process.pid
                
                # Notify on start
                if self.config.on_start:
                    try:
                        self.config.on_start(result.pid)
                    except Exception as e:
                        log.warning(f"on_start callback error: {e}")
                
                log.info(f"Process started with PID: {result.pid}")
                
                # Handle output
                if self.config.capture_output or self.config.stream_output:
                    try:
                        stdout, stderr = self._stream_output(self._process)
                        result.stdout = stdout if stdout else None
                        result.stderr = stderr if stderr else None
                        return_code = self._process.wait(timeout=self.config.timeout)
                    except subprocess.TimeoutExpired:
                        log.error(f"Process timed out after {self.config.timeout}s")
                        self._terminate_process()
                        result.timed_out = True
                        return_code = -1
                else:
                    try:
                        return_code = self._process.wait(timeout=self.config.timeout)
                    except subprocess.TimeoutExpired:
                        log.error(f"Process timed out after {self.config.timeout}s")
                        self._terminate_process()
                        result.timed_out = True
                        return_code = -1
                
                result.return_code = return_code
                result.execution_time = time.time() - start_time
                
                if self._interrupted:
                    log.warning("Process was interrupted")
                    result.return_code = -2
                
                log.info(f"Process finished: {result}")
                
        except (PreRunError, PostRunError):
            # Re-raise wrapper errors
            raise
        except Exception as e:
            result.execution_time = time.time() - start_time
            log.error(f"Execution failed: {e}")
            if self.config.raise_on_error:
                raise ExecutionError(f"Execution failed: {e}") from e
        finally:
            self._process = None
            
            # Post-run operations (always execute if configured)
            try:
                self._execute_post_run(result)
            except PostRunError:
                if not self.config.continue_on_post_run_error:
                    raise
        
        # Check for errors
        if self.config.raise_on_error and not result.success:
            if result.timed_out:
                raise ExecutionError(f"Process timed out after {self.config.timeout}s")
            elif result.return_code != 0:
                raise ExecutionError(
                    f"Process exited with code {result.return_code}\n"
                    f"Command: {' '.join(result.command)}"
                )
        
        return result
    
    def __call__(self) -> ExecutionResult:
        """Allow wrapper to be called as a function.
        
        """
        return self.run()
    
    @contextmanager
    def __enter__(self):
        """Context manager entry.
        
        """
        yield self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup if process is still running.
        
        """
        if self._process:
            self._terminate_process()


def create_wrapper(
    executable: str | Path,
    *args: str,
    env: dict[str, str] | None = None,
    env_files: str | Path | list[str | Path] | None = None,
    pre_run: Callable[[], None] | None = None,
    post_run: Callable[[ExecutionResult], None] | None = None,
    **kwargs
) -> ApplicationWrapper:
    """Convenience function to create an ApplicationWrapper.
    
    Args:
        executable: Path to executable or command name
        *args: Command-line arguments
        env: Environment variables to add/update
        env_files: JSON file(s) containing environment variables
        pre_run: Pre-run callback
        post_run: Post-run callback
        **kwargs: Additional WrapperConfig parameters
        
    Returns:
        Configured ApplicationWrapper instance
        
    Example:
        >>> wrapper = create_wrapper(
        ...     "python", "script.py", "--verbose",
        ...     env_files="config/env.json",
        ...     timeout=60
        ... )
        >>> result = wrapper.run()
        
    """
    config = WrapperConfig(
        executable=executable,
        args=list(args),
        env=env,
        env_files=env_files,
        pre_run=pre_run,
        post_run=post_run,
        **kwargs
    )
    return ApplicationWrapper(config)
