"""Tests for configuration management."""

import json
import pytest
from pathlib import Path
from md_editor.config import Config


def test_config_default():
    """Test default configuration."""
    config = Config.default()
    assert config.resource_files == []
    assert config.claude_command == "claude"


def test_config_load_nonexistent(tmp_path, monkeypatch):
    """Test loading config when file doesn't exist."""
    # Mock config path to tmp directory
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: config_path))

    config = Config.load()
    assert config.resource_files == []
    assert config.claude_command == "claude"
    assert config_path.exists()


def test_config_save_and_load(tmp_path, monkeypatch):
    """Test saving and loading configuration."""
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: config_path))

    # Create and save config
    config = Config(
        resource_files=["file1.md", "file2.md"],
        claude_command="custom-claude"
    )
    config.save()

    # Load it back
    loaded_config = Config.load()
    assert loaded_config.resource_files == ["file1.md", "file2.md"]
    assert loaded_config.claude_command == "custom-claude"


def test_validate_resource_files(tmp_path):
    """Test validation of resource files."""
    # Create some test files
    file1 = tmp_path / "exists.md"
    file1.write_text("# Test")

    config = Config(
        resource_files=[
            str(file1),
            str(tmp_path / "nonexistent.md")
        ]
    )

    valid_files = config.validate_resource_files()
    assert len(valid_files) == 1
    assert str(file1) in valid_files
