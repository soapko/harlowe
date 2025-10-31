"""Configuration management for md-editor."""

import json
import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class Config:
    """Configuration for md-editor."""

    resource_files: List[str]
    claude_command: str = "claude"
    threads_dir: Optional[str] = None  # Optional custom directory for thread storage

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the config file."""
        config_dir = Path.home() / ".config" / "md-editor"
        return config_dir / "config.json"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file or create default."""
        config_path = cls.get_config_path()

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                return cls(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Could not load config: {e}. Using defaults.")
                return cls.default()
        else:
            # Create default config
            config = cls.default()
            config.save()
            return config

    @classmethod
    def default(cls) -> "Config":
        """Create default configuration."""
        return cls(
            resource_files=[],
            claude_command="claude",
            threads_dir=None  # Defaults to .harlowe directory next to file
        )

    def save(self) -> None:
        """Save configuration to file."""
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    def validate_resource_files(self) -> List[str]:
        """Validate that resource files exist and return valid ones."""
        valid_files = []
        for file_path in self.resource_files:
            path = Path(file_path).expanduser()
            if path.exists() and path.is_file():
                valid_files.append(str(path))
            else:
                print(f"Warning: Resource file not found: {file_path}")
        return valid_files
