"""Test package discovery functionality."""

from pathlib import Path
from gt.app.wrapper._discovery import (
    validate_package,
    load_packages_from_config,
    get_packages
)

def test_validation():
    """Test package validation."""
    print("Testing package validation...")
    
    examples_path = Path(__file__).parent / "examples"
    print(f"Checking: {examples_path}")
    print(f"  Is valid package: {validate_package(examples_path)}")
    print(f"  Has wrapper_env: {(examples_path / 'wrapper_env').is_dir()}")
    print()

def test_config_loading():
    """Test loading packages from config."""
    print("Testing config-based package loading...")
    
    config_file = Path(__file__).parent / "examples" / "packages.json"
    print(f"Config file: {config_file}")
    print(f"  Exists: {config_file.exists()}")
    
    if config_file.exists():
        try:
            packages = load_packages_from_config(config_file)
            print(f"  Loaded {len(packages)} package(s)")
            for pkg in packages:
                print(f"    - {pkg}")
        except Exception as e:
            print(f"  Error: {e}")
    print()

def test_auto_discovery():
    """Test auto-discovery with DO_PKG_ROOTS."""
    import os
    print("Testing auto-discovery...")
    
    # Set DO_PKG_ROOTS to parent directory
    parent_dir = str(Path(__file__).parent.parent.parent.parent.parent.parent)
    os.environ['DO_PKG_ROOTS'] = parent_dir
    print(f"DO_PKG_ROOTS: {parent_dir}")
    
    try:
        packages = get_packages()
        print(f"  Auto-discovered {len(packages)} package(s)")
        for pkg in packages:
            print(f"    - {pkg}")
    except Exception as e:
        print(f"  Error: {e}")
    print()

if __name__ == '__main__':
    test_validation()
    test_config_loading()
    test_auto_discovery()
