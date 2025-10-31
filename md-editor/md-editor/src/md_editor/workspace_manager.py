"""Ephemeral workspace system for isolated Claude execution."""

import hashlib
import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import difflib


logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """Represents changes to a single file."""
    file_path: Path
    unified_diff: str
    original_checksum: str
    new_checksum: str
    lines_added: int = 0
    lines_removed: int = 0
    lines_modified: int = 0

    @classmethod
    def from_diff(cls, file_path: Path, original_content: str, new_content: str) -> Optional["FileChange"]:
        """Create FileChange from file contents."""
        # Calculate checksums
        original_checksum = hashlib.sha256(original_content.encode()).hexdigest()
        new_checksum = hashlib.sha256(new_content.encode()).hexdigest()

        # If identical, no change
        if original_checksum == new_checksum:
            return None

        # Generate unified diff
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_gen = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"original/{file_path.name}",
            tofile=f"workspace/{file_path.name}",
            lineterm=''
        )
        unified_diff = '\n'.join(diff_gen)

        # Count changes
        lines_added = 0
        lines_removed = 0
        for line in unified_diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                lines_added += 1
            elif line.startswith('-') and not line.startswith('---'):
                lines_removed += 1

        return cls(
            file_path=file_path,
            unified_diff=unified_diff,
            original_checksum=original_checksum,
            new_checksum=new_checksum,
            lines_added=lines_added,
            lines_removed=lines_removed,
            lines_modified=min(lines_added, lines_removed)
        )


@dataclass
class WorkspaceChanges:
    """All changes from a workspace."""
    thread_id: str
    message_id: str
    timestamp: datetime
    files_changed: Dict[Path, FileChange] = field(default_factory=dict)

    @property
    def total_changes(self) -> int:
        """Total number of line changes across all files."""
        return sum(
            fc.lines_added + fc.lines_removed
            for fc in self.files_changed.values()
        )

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return len(self.files_changed) > 0


@dataclass
class WorkspaceInfo:
    """Information about created workspace."""
    workspace_dir: Path
    workspace_file: Path
    resource_files: List[Path]
    original_checksums: Dict[Path, str]


class EphemeralWorkspace:
    """
    Context manager for temporary isolated workspace.

    Creates a temporary directory with copies of files for Claude to operate on.
    Automatically captures changes and cleans up afterward.
    """

    def __init__(
        self,
        source_file: Path,
        thread_id: str,
        message_id: str,
        resource_files: Optional[List[Path]] = None
    ):
        """
        Initialize ephemeral workspace.

        Args:
            source_file: Main markdown file being edited
            thread_id: Thread identifier
            message_id: Message identifier (for unique workspace)
            resource_files: Additional files to include in workspace
        """
        self.source_file = Path(source_file).resolve()
        self.thread_id = thread_id
        self.message_id = message_id
        self.resource_files = [Path(f).resolve() for f in (resource_files or [])]

        # Create unique workspace directory
        timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
        self.workspace_dir = Path(f"/tmp/harlowe_ws_{thread_id}_{message_id}_{timestamp}")
        self.workspace_file = self.workspace_dir / self.source_file.name

        self._workspace_info: Optional[WorkspaceInfo] = None
        self._original_contents: Dict[Path, str] = {}
        self._preserve_for_debug = False

    def __enter__(self) -> WorkspaceInfo:
        """Create workspace and return info."""
        logger.info(f"Creating workspace: {self.workspace_dir}")

        # Create workspace directory
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Copy main file
        self._copy_file(self.source_file, self.workspace_file)

        # Copy resource files
        workspace_resource_files = []
        for resource_file in self.resource_files:
            workspace_resource = self.workspace_dir / resource_file.name
            self._copy_file(resource_file, workspace_resource)
            workspace_resource_files.append(workspace_resource)

        # Calculate original checksums
        original_checksums = {}
        for path, content in self._original_contents.items():
            checksum = hashlib.sha256(content.encode()).hexdigest()
            original_checksums[path] = checksum

        self._workspace_info = WorkspaceInfo(
            workspace_dir=self.workspace_dir,
            workspace_file=self.workspace_file,
            resource_files=workspace_resource_files,
            original_checksums=original_checksums
        )

        logger.info(f"Workspace created with {len(workspace_resource_files)} resource files")
        return self._workspace_info

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup workspace."""
        if self._preserve_for_debug:
            logger.warning(f"Preserving workspace for debugging: {self.workspace_dir}")
            return

        try:
            if self.workspace_dir.exists():
                shutil.rmtree(self.workspace_dir)
                logger.info(f"Cleaned up workspace: {self.workspace_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup workspace {self.workspace_dir}: {e}")
            # Non-fatal: /tmp will be cleaned by OS eventually

    def _copy_file(self, source: Path, dest: Path) -> None:
        """
        Copy a file and store its original content.

        Args:
            source: Source file path
            dest: Destination file path
        """
        if not source.exists():
            logger.warning(f"Source file does not exist: {source}")
            return

        # Read and store original content
        content = source.read_text()
        self._original_contents[source] = content

        # Write to destination
        dest.write_text(content)
        logger.debug(f"Copied: {source.name} -> {dest}")

    def get_changes(self) -> WorkspaceChanges:
        """
        Generate changes between workspace and original files.

        Returns:
            WorkspaceChanges object with all file changes
        """
        changes = WorkspaceChanges(
            thread_id=self.thread_id,
            message_id=self.message_id,
            timestamp=datetime.now()
        )

        # Check each file that was copied to workspace
        for original_path, original_content in self._original_contents.items():
            workspace_path = self.workspace_dir / original_path.name

            if not workspace_path.exists():
                # File was deleted in workspace
                logger.warning(f"File deleted in workspace: {original_path.name}")
                continue

            # Read workspace version
            try:
                workspace_content = workspace_path.read_text()
            except Exception as e:
                logger.error(f"Failed to read workspace file {workspace_path}: {e}")
                continue

            # Generate diff if changed
            file_change = FileChange.from_diff(original_path, original_content, workspace_content)
            if file_change:
                changes.files_changed[original_path] = file_change
                logger.info(
                    f"Detected changes in {original_path.name}: "
                    f"+{file_change.lines_added} -{file_change.lines_removed}"
                )

        return changes

    def preserve_for_debugging(self) -> None:
        """Skip cleanup to preserve workspace for debugging."""
        self._preserve_for_debug = True
        logger.info(f"Workspace will be preserved: {self.workspace_dir}")


class WorkspaceManager:
    """High-level workspace operations and management."""

    @staticmethod
    def cleanup_orphaned_workspaces(max_age_hours: int = 24) -> int:
        """
        Clean up stale workspaces from /tmp.

        Args:
            max_age_hours: Maximum age in hours before cleaning up workspace

        Returns:
            Number of workspaces cleaned up
        """
        tmp_dir = Path("/tmp")
        pattern = "harlowe_ws_*"
        count = 0

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        for workspace_dir in tmp_dir.glob(pattern):
            if not workspace_dir.is_dir():
                continue

            try:
                # Check modification time
                mtime = datetime.fromtimestamp(workspace_dir.stat().st_mtime)
                if mtime < cutoff_time:
                    shutil.rmtree(workspace_dir)
                    count += 1
                    logger.info(f"Cleaned up orphaned workspace: {workspace_dir.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup orphaned workspace {workspace_dir}: {e}")

        return count

    @staticmethod
    def get_workspace_size(workspace_dir: Path) -> int:
        """
        Get disk usage of workspace in bytes.

        Args:
            workspace_dir: Path to workspace directory

        Returns:
            Size in bytes
        """
        if not workspace_dir.exists():
            return 0

        total_size = 0
        try:
            for file_path in workspace_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"Failed to calculate workspace size: {e}")

        return total_size

    @staticmethod
    def list_active_workspaces() -> List[Path]:
        """
        List all active Harlowe workspaces in /tmp.

        Returns:
            List of workspace directory paths
        """
        tmp_dir = Path("/tmp")
        pattern = "harlowe_ws_*"

        workspaces = []
        for workspace_dir in tmp_dir.glob(pattern):
            if workspace_dir.is_dir():
                workspaces.append(workspace_dir)

        return workspaces

    @staticmethod
    def init_workspace_cleanup() -> int:
        """
        Initialize workspace cleanup on application start.

        Cleans up any orphaned workspaces from previous sessions.

        Returns:
            Number of workspaces cleaned up
        """
        logger.info("Performing initial workspace cleanup...")
        count = WorkspaceManager.cleanup_orphaned_workspaces(max_age_hours=0)
        if count > 0:
            logger.info(f"Cleaned up {count} orphaned workspace(s)")
        return count
