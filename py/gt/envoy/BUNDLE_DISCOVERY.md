# Bundle Discovery Feature

## Overview

The wrapper now supports discovering and loading commands from multiple bundles, enabling centralized management of development environments across multiple repositories.

## Discovery Methods

### 1. Auto-Discovery (ENVOY_BNDL_ROOTS)

Automatically discover bundles by searching for Git repositories in specified root directories.

#### Setup

Set the `ENVOY_BNDL_ROOTS` environment variable with root directories to search:

```bash
# Windows
set ENVOY_BNDL_ROOTS=R:\repo;D:\projects

# Linux/Mac  
export ENVOY_BNDL_ROOTS=/home/user/repos:/opt/projects
```

#### How it Works

1. Searches each root directory for subdirectories containing `.git` folders
2. Validates each Git repository by checking for an `envoy_env/` directory
3. Loads commands from`envoy_env/commands.json` in each valid bundle
4. Commands from all bundles are merged into a single registry

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
    └── not-a-bundle\
```

Auto-discovery would find `project-a` and `project-b`.

### 2. Config File Discovery

Explicitly specify bundles in a JSON configuration file.

#### Config File Format

```json
{
  "bundles": [
    "/absolute/path/to/bundle1",
    "R:\\Windows\\Path\\to\\bundle2",
    "/another/bundle"
  ]
}
```

Or simplified array format:

```json
[
  "/path/to/bundle1",
  "/path/to/bundle2"
]
```

#### Usage

```bash
# Using config file
do --bundles-config /path/to/bundles.json --list

# With python -m
python -m gt.envoy --bundles-config bundles.json --list
```

## CLI Integration

### New Command-Line Option

```bash
--bundles-config PATH    Path to bundles config file
```

### Command Listing with Bundles

Commands now show their source bundle:

```bash
$ do --bundles-config bundles.json --list

Available commands:

  python_dev           → python [my-bundle]
  build_tools          → make [build-system]
  test_runner          → pytest [test-framework]
```

### Command Info with Bundle Details

```bash
$ do --bundles-config bundles.json --info python_dev

Command: python_dev
Bundle: my-bundle
Executable: python
Environment files:
  - dev_env.json
Environment directory: /path/to/my-bundle/envoy_env
Alias: python
```

## Bundle Structure

A valid bundle must:

1. Have an `envoy_env/` directory
2. Optionally include `envoy_env/commands.json` for command definitions
3. Optionally include environment JSON files in `envoy_env/`

```
my-bundle/
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

1. **Config File**: If `--bundles-config` is specified, only those bundles are loaded
2. **Auto-Discovery**: If no config file, attempts auto-discovery via `ENVOY_BNDL_ROOTS`
3. **Local Fallback**: If no bundles found, falls back to local `envoy_env/commands.json`

### Command Conflicts

If multiple bundles define the same command name, the last loaded bundle wins. A warning is logged:

```
WARNING - Command 'python_dev' from bundle2 overrides existing command from bundle1
```

## Examples

### Example 1: Using Config File

Create `bundles.json`:

```json
{
  "bundles": [
    "R:\\repo\\my-app",
    "R:\\repo\\shared-tools"
  ]
}
```

List all commands:

```bash
do --bundles-config bundles.json --list
```

Execute a command:

```bash
do --bundles-config bundles.json python_dev script.py
```

### Example 2: Auto-Discovery

Set environment variable:

```bash
set ENVOY_BNDL_ROOTS=R:\repo;D:\projects
```

Auto-discover and list:

```bash
do --list
```

### Example 3: Mixed Environments

Bundle 1 (`app-framework/envoy_env/commands.json`):

```json
{
  "python_dev": {
    "environment": ["python39.json"],
    "alias": ["python"]
  }
}
```

Bundle 2 (`tools/envoy_env/commands.json`):

```json
{
  "build": {
    "environment": ["build_env.json"],
    "alias": ["make", "build"]
  }
}
```

Both commands are available when bundles are discovered:

```bash
$ do --list

Available commands:

  python_dev           → python [app-framework]
  build                → make build [tools]
```

## Python API

### Programmatic Access

```python
from gt.envoy import get_bundles, BundleInfo

# Auto-discovery
bundles = get_bundles()

# From config file
from pathlib import Path
config = Path("bundles.json")
bundles = get_bundles(config_file=config)

# Inspect bundles
for bundle in bundles:
    print(f"{bundle.name}: {bundle.root}")
    print(f"  Envoy env: {bundle.envoy_env}")
```

### Command Registry with Bundles

```python
from gt.envoy import CommandRegistry, get_bundles

# Load from multiple bundles
registry = CommandRegistry()
bundles = get_bundles()
registry.load_from_bundles(bundles)

# Access commands with bundle info
for cmd_name in registry.list_commands():
    cmd = registry.get(cmd_name)
    print(f"{cmd_name} from {cmd.bundle}")
```

## Environment Variable Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVOY_BNDL_ROOTS` | Semicolon-separated (Windows) or colon-separated (Unix) list of root directories to search for bundles | `R:\repo;D:\projects` |
2. **Team Collaboration**: Share bundle configurations via version control
3. **Flexible Discovery**: Choose between auto-discovery or explicit configuration
4. **Namespace Clarity**: Bundle names show command sources
5. **Environment Isolation**: Each bundle maintains its own environment files

## Troubleshooting

### No bundles found

```
Error: No commands loaded
```

**Solutions**:
- Verify `ENVOY_BNDL_ROOTS` is set correctly
- Check that bundles have `envoy_env/` directories
- Use `--bundles-config` with explicit paths
- Ensure Git repositories have `.git` folders for auto-discovery

### Bundle not discovered

**Check**:
1. Bundle has `envoy_env/` directory
2. For auto-discovery: bundle has `.git/` folder
3. Bundle path is in `ENVOY_BNDL_ROOTS` or config file
4. Path separators match OS (`;` Windows, `:` Unix)

### Command not found

```bash
# Use --verbose to see bundle loading
do --bundles-config bundles.json --verbose python_dev
```

This shows which bundles are loaded and which commands are available.

## Migration from Single Bundle

### Before (single bundle)

```bash
cd my-project
do python_dev script.py
```

### After (multi-bundle)

```bash
# Option 1: Config file
do --bundles-config ~/my-bundles.json python_dev script.py

# Option 2: Auto-discovery
set ENVOY_BNDL_ROOTS=R:\repo
do python_dev script.py

# Option 3: Still works locally
cd my-project
do python_dev script.py
```

## Advanced Usage

### Combining Multiple Environments

Commands can load multiple environment files from their bundle:

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

### Bundle-Specific Paths

Environment files use `{$__BUNDLE__}` for bundle-relative paths:

```json
{
  "PYTHONPATH": [
    "{$__BUNDLE__}/src",
    "{$__BUNDLE__}/lib"
  ]
}
```

This ensures paths resolve correctly regardless of bundle location.
