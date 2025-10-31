"""Manages resource file associations for markdown documents."""

import json
from pathlib import Path
from typing import List, Dict, Optional


class ResourceFileManager:
    """Manages persistent storage of resource file associations."""

    RESOURCE_FILE_NAME = ".md-editor-resources.json"

    def __init__(self, markdown_file_path: str):
        """Initialize the resource file manager.

        Args:
            markdown_file_path: Path to the markdown file being edited
        """
        self.markdown_file_path = Path(markdown_file_path).absolute()
        self.project_dir = self.markdown_file_path.parent
        self.resource_file_path = self.project_dir / self.RESOURCE_FILE_NAME
        self._data: Dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        """Load resource associations from disk."""
        if self.resource_file_path.exists():
            try:
                with open(self.resource_file_path, 'r') as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted or unreadable, start fresh
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Save resource associations to disk."""
        try:
            with open(self.resource_file_path, 'w') as f:
                json.dump(self._data, f, indent=2)
        except IOError:
            # Silently fail if we can't write (e.g., read-only filesystem)
            pass

    def get_resources(self) -> List[str]:
        """Get resource files for the current markdown file.

        Returns:
            List of absolute paths to resource files
        """
        key = str(self.markdown_file_path)
        resources = self._data.get(key, [])

        # Filter out resources that no longer exist
        valid_resources = []
        for resource in resources:
            resource_path = Path(resource)
            if resource_path.exists() and resource_path.is_file():
                valid_resources.append(resource)

        # Update if we filtered any out
        if len(valid_resources) != len(resources):
            self.set_resources(valid_resources)

        return valid_resources

    def set_resources(self, resource_files: List[str]) -> None:
        """Set resource files for the current markdown file.

        Args:
            resource_files: List of absolute paths to resource files
        """
        key = str(self.markdown_file_path)

        # Convert all paths to absolute
        absolute_resources = [str(Path(r).absolute()) for r in resource_files]

        if absolute_resources:
            self._data[key] = absolute_resources
        else:
            # Remove entry if no resources selected
            self._data.pop(key, None)

        self._save()

    def get_available_markdown_files(self) -> List[Path]:
        """Get all markdown files in the same directory (excluding current file).

        Returns:
            List of Path objects for markdown files
        """
        markdown_files = []

        # Find all .md and .markdown files
        for pattern in ["*.md", "*.markdown"]:
            markdown_files.extend(self.project_dir.glob(pattern))

        # Filter out the current file and sort
        markdown_files = [
            f for f in markdown_files
            if f.absolute() != self.markdown_file_path
        ]
        markdown_files.sort(key=lambda p: p.name.lower())

        return markdown_files
