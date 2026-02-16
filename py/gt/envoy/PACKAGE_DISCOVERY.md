# Package Discovery Feature

## Overview

The wrapper now supports discovering and loading commands from multiple packages, enabling centralized management of development environments across multiple repositories.

## Discovery Methods

### 1. Auto-Discovery (DO_PKG_ROOTS)

Automatically discover packages by searching for Git repositories in specified root directories.

#### Setup

Set the `DO_PKG_ROOTS` environment variable with root directories to search:

```bash
# Windows
set DO_PKG_ROOTS=R:\repo;D:\projects

# Linux/Mac  
export DO_PKG_ROOTS=/home/user/repos:/opt/projects
```

#### How it Works

1. Searches each root directory for subdirectories containing `.git` folders
2. Validates each Git repository by checking for an `envoy_env/` directory
3. Loads commands from`envoy_env/commands.json` in each valid package
4. Commands from all packages are merged into a single registry

#### Example Structure

```
R:\repo\
├── project-a\
│   ├── .git\
│   └── envoy_env\
│       ├── commands.json
│       └── env.json
├── project-b\
│   ├── .git\
│   └── envoy_env\
│       ├── commands.json
│       └── env.json
└── other-folder\
    └── not-a-package\
```

Auto-discovery would find `project-a` and `project-b`.

### 2. Config File Discovery

Explicitly specify packages in a JSON configuration file.

#### Config File Format

```json
{
  "packages": [
    "/absolute/path/to/package1",
    "R:\\Windows\\Path\\to\\package2",
    "/another/package"
  ]
}
```

Or simplified array format:

```json
[
  "/path/to/package1",
  "/path/to/package2"
]
```

#### Usage

```bash
# Using config file
do --packages-config /path/to/packages.json --list

# With python -m
python -m gt.app.wrapper --packages-config packages.json --list
```

## CLI Integration

### New Command-Line Option

```bash
--packages-config PATH    Path to packages config file
```

### Command Listing with Packages

Commands now show their source package:

```bash
$ do --packages-config packages.json --list

Available commands:

  python_dev           → python [my-package]
  build_tools          → make [build-system]
  test_runner          → pytest [test-framework]
```

### Command Info with Package Details

```bash
$ do --packages-config packages.json --info python_dev

Command: python_dev
Package: my-package
Executable: python
Environment files:
  - dev_env.json
Environment directory: /path/to/my-package/envoy_env
Alias: python
```

## Package Structure

A valid package must:

1. Have an `envoy_env/` directory
2. Optionally include `envoy_env/commands.json` for command definitions
3. Optionally include environment JSON files in `envoy_env/`

```
my-package/
├── .git/                      # Optional (for auto-discovery)
├── envoy_env/
│   ├── commands.json          # Command definitions
│   ├── base_env.json          # Environment variables
│   └── dev_env.json           # Additional environments
└── src/
    └── ...
```

## Priority and Conflict Resolution

### Loading Order

1. **Config File**: If `--packages-config` is specified, only those packages are loaded
2. **Auto-Discovery**: If no config file, attempts auto-discovery via `DO_PKG_ROOTS`
3. **Local Fallback**: If no packages found, falls back to local `envoy_env/commands.json`

### Command Conflicts

If multiple packages define the same command name, the last loaded package wins. A warning is logged:

```
WARNING - Command 'python_dev' from package2 overrides existing command from package1
```

## Examples

### Example 1: Using Config File

Create `packages.json`:

```json
{
  "packages": [
    "R:\\repo\\my-app",
    "R:\\repo\\shared-tools"
  ]
}
```

List all commands:

```bash
do --packages-config packages.json --list
```

Execute a command:

```bash
do --packages-config packages.json python_dev script.py
```

### Example 2: Auto-Discovery

Set environment variable:

```bash
set DO_PKG_ROOTS=R:\repo;D:\projects
```

Auto-discover and list:

```bash
do --list
```

### Example 3: Mixed Environments

Package 1 (`app-framework/envoy_env/commands.json`):

```json
{
  "python_dev": {
    "environment": ["python39.json"],
    "alias": ["python"]
  }
}
```

Package 2 (`tools/envoy_env/commands.json`):

```json
{
  "build": {
    "environment": ["build_env.json"],
    "alias": ["make", "build"]
  }
}
```

Both commands are available when packages are discovered:

```bash
$ do --list

Available commands:

  python_dev           → python [app-framework]
  build                → make build [tools]
```

## Python API

### Programmatic Access

```python
from gt.app.wrapper import get_packages, PackageInfo

# Auto-discovery
packages = get_packages()

# From config file
from pathlib import Path
config = Path("packages.json")
packages = get_packages(config_file=config)

# Inspect packages
for pkg in packages:
    print(f"{pkg.name}: {pkg.root}")
    print(f"  Envoy env: {pkg.envoy_env}")
```

### Command Registry with Packages

```python
from gt.app.wrapper import CommandRegistry, get_packages

# Load from multiple packages
registry = CommandRegistry()
packages = get_packages()
registry.load_from_packages(packages)

# Access commands with package info
for cmd_name in registry.list_commands():
    cmd = registry.get(cmd_name)
    print(f"{cmd_name} from {cmd.package}")
```

## Environment Variable Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `DO_PKG_ROOTS` | Semicolon-separated (Windows) or colon-separated (Unix) list of root directories to search for packages | `R:\repo;D:\projects` |

## Benefits

1. **Centralized Management**: Manage commands across multiple repositories
2. **Team Collaboration**: Share package configurations via version control
3. **Flexible Discovery**: Choose between auto-discovery or explicit configuration
4. **Namespace Clarity**: Package names show command sources
5. **Environment Isolation**: Each package maintains its own environment files

## Troubleshooting

### No packages found

```
Error: No commands loaded
```

**Solutions**:
- Verify `DO_PKG_ROOTS` is set correctly
- Check that packages have `envoy_env/` directories
- Use `--packages-config` with explicit paths
- Ensure Git repositories have `.git` folders for auto-discovery

### Package not discovered

**Check**:
1. Package has `envoy_env/` directory
2. For auto-discovery: package has `.git/` folder
3. Package path is in `DO_PKG_ROOTS` or config file
4. Path separators match OS (`;` Windows, `:` Unix)

### Command not found

```bash
# Use --verbose to see package loading
do --packages-config packages.json --verbose python_dev
```

This shows which packages are loaded and which commands are available.

## Migration from Single Package

### Before (single package)

```bash
cd my-project
do python_dev script.py
```

### After (multi-package)

```bash
# Option 1: Config file
do --packages-config ~/my-packages.json python_dev script.py

# Option 2: Auto-discovery
set DO_PKG_ROOTS=R:\repo
do python_dev script.py

# Option 3: Still works locally
cd my-project
do python_dev script.py
```

## Advanced Usage

### Combining Multiple Environments

Commands can load multiple environment files from their package:

```json
{
  "full_stack": {
    "environment": [
      "base_env.json",
      "python_env.json",
      "node_env.json",
      "database_env.json"
    ],
    "alias": ["python", "-m", "myapp"]
  }
}
```

### Package-Specific Paths

Environment files use `{$__PACKAGE__}` for package-relative paths:

```json
{
  "PYTHONPATH": [
    "{$__PACKAGE__}/src",
    "{$__PACKAGE__}/lib"
  ]
}
```

This ensures paths resolve correctly regardless of package location.
