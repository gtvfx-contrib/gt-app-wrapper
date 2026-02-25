"""Tests for the CLI module."""

import json
import sys
import io
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from envoy._commands import CommandRegistry
from envoy._cli import show_command_info


def _make_registry(commands: dict) -> CommandRegistry:
    """Create a CommandRegistry from a dict of command definitions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "commands.json"
        f.write_text(json.dumps(commands))
        registry = CommandRegistry(f)
    return registry


def test_show_command_info_resolves_inherited_environment(capsys):
    """show_command_info should display the fully resolved env file list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmds = {
            "base": {"environment": ["base_env.json"]},
            "derived": {"environment": ["base", "derived_env.json"], "alias": ["derived_prog"]},
        }
        f = Path(tmpdir) / "commands.json"
        f.write_text(json.dumps(cmds))
        registry = CommandRegistry(f)

    rc = show_command_info(registry, "derived")
    captured = capsys.readouterr()

    assert rc == 0
    # Inherited file should be expanded, not shown as raw reference
    assert "base_env.json" in captured.out
    assert "derived_env.json" in captured.out
    # The raw command-name reference must NOT appear as an entry
    lines = [ln.strip() for ln in captured.out.splitlines()]
    assert "- base" not in lines


def test_show_command_info_wrappererror_returns_1(capsys):
    """show_command_info should return 1 and print to stderr on WrapperError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # "broken" references a command that does not exist
        cmds = {"broken": {"environment": ["nonexistent_cmd"]}}
        f = Path(tmpdir) / "commands.json"
        f.write_text(json.dumps(cmds))
        registry = CommandRegistry(f)

    rc = show_command_info(registry, "broken")
    captured = capsys.readouterr()

    assert rc == 1
    assert "Error" in captured.err
    assert "broken" in captured.err
