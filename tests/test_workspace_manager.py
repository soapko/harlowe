"""Unit tests for WorkspaceManager."""

import pytest
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta
from harlowe.workspace_manager import (
    EphemeralWorkspace,
    WorkspaceManager,
    FileChange,
    WorkspaceChanges,
    WorkspaceInfo
)


@pytest.fixture
def temp_document():
    """Create a temporary markdown document."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Test Document\n\nThis is test content.\n")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_resource_files():
    """Create temporary resource files."""
    files = []
    for i in range(2):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(f"# Resource {i}\n\nResource content {i}.\n")
            files.append(Path(f.name))

    yield files

    # Cleanup
    for f in files:
        f.unlink(missing_ok=True)


class TestEphemeralWorkspaceCreation:
    """Test workspace creation and initialization."""

    def test_workspace_creation(self, temp_document):
        """Test basic workspace creation."""
        with EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        ) as workspace:
            assert workspace.workspace_dir.exists()
            assert workspace.workspace_file.exists()
            assert workspace.workspace_file.read_text() == temp_document.read_text()

        # Workspace should be cleaned up after context exit
        assert not workspace.workspace_dir.exists()

    def test_workspace_with_resource_files(self, temp_document, temp_resource_files):
        """Test workspace creation with resource files."""
        with EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1",
            resource_files=temp_resource_files
        ) as workspace:
            assert len(workspace.resource_files) == 2
            for resource in workspace.resource_files:
                assert resource.exists()
                # Verify content matches original
                original_name = resource.name
                original = next(f for f in temp_resource_files if f.name == original_name)
                assert resource.read_text() == original.read_text()

    def test_workspace_unique_names(self, temp_document):
        """Test that each workspace gets a unique directory name."""
        workspaces = []
        for i in range(3):
            ws = EphemeralWorkspace(
                source_file=temp_document,
                thread_id="test-thread",
                message_id=f"msg-{i}"
            )
            workspaces.append(ws)
            time.sleep(0.01)  # Small delay to ensure unique timestamps

        # All workspace dirs should be different
        dirs = [ws.workspace_dir for ws in workspaces]
        assert len(set(dirs)) == 3

    def test_workspace_info_checksums(self, temp_document):
        """Test that workspace info includes original checksums."""
        ws = EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        )
        with ws as workspace:
            assert len(workspace.original_checksums) > 0
            # Use resolved path for comparison
            assert temp_document.resolve() in workspace.original_checksums


class TestChangeDetection:
    """Test file change detection and diff generation."""

    def test_no_changes(self, temp_document):
        """Test that no changes are detected when files unchanged."""
        with EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        ) as workspace:
            # Don't modify anything
            pass

        # Get changes before cleanup (re-enter context)
        workspace = EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        )
        with workspace:
            changes = workspace.get_changes()

        assert not changes.has_changes
        assert changes.total_changes == 0

    def test_detect_file_modification(self, temp_document):
        """Test detecting file modifications."""
        ws = EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        )
        with ws as workspace:
            # Modify the workspace file
            new_content = "# Modified Document\n\nThis is new content.\n"
            workspace.workspace_file.write_text(new_content)

            # Get changes
            changes = ws.get_changes()

        assert changes.has_changes
        assert len(changes.files_changed) == 1
        assert temp_document.resolve() in changes.files_changed

        file_change = changes.files_changed[temp_document.resolve()]
        assert file_change.lines_added > 0 or file_change.lines_removed > 0
        assert file_change.unified_diff != ""

    def test_detect_line_additions(self, temp_document):
        """Test detecting line additions."""
        ws = EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        )
        with ws as workspace:
            # Add lines to the file
            original = workspace.workspace_file.read_text()
            workspace.workspace_file.write_text(original + "\nNew line 1\nNew line 2\n")

            changes = ws.get_changes()

        file_change = changes.files_changed[temp_document.resolve()]
        assert file_change.lines_added >= 2

    def test_detect_line_removals(self, temp_document):
        """Test detecting line removals."""
        ws = EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        )
        with ws as workspace:
            # Remove content
            workspace.workspace_file.write_text("# Test Document\n")

            changes = ws.get_changes()

        file_change = changes.files_changed[temp_document.resolve()]
        assert file_change.lines_removed > 0

    def test_unified_diff_format(self, temp_document):
        """Test that unified diff is in correct format."""
        ws = EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        )
        with ws as workspace:
            workspace.workspace_file.write_text("# Changed\n")
            changes = ws.get_changes()

        file_change = changes.files_changed[temp_document.resolve()]
        diff = file_change.unified_diff

        # Should contain diff markers
        assert "---" in diff or "+++" in diff or diff == ""  # empty if no changes
        if diff:
            assert "-" in diff or "+" in diff


class TestFileChange:
    """Test FileChange functionality."""

    def test_file_change_from_identical_content(self):
        """Test that identical content produces no change."""
        content = "Same content\n"
        change = FileChange.from_diff(
            Path("test.md"),
            content,
            content
        )
        assert change is None

    def test_file_change_from_different_content(self):
        """Test that different content produces a change."""
        original = "Original content\n"
        modified = "Modified content\n"
        change = FileChange.from_diff(
            Path("test.md"),
            original,
            modified
        )

        assert change is not None
        assert change.original_checksum != change.new_checksum
        assert change.lines_added > 0
        assert change.lines_removed > 0

    def test_file_change_checksums(self):
        """Test that checksums are calculated correctly."""
        original = "Test content\n"
        modified = "Different content\n"
        change = FileChange.from_diff(
            Path("test.md"),
            original,
            modified
        )

        # Checksums should be hex strings
        assert len(change.original_checksum) == 64  # SHA-256
        assert len(change.new_checksum) == 64
        assert change.original_checksum != change.new_checksum


class TestWorkspaceCleanup:
    """Test workspace cleanup functionality."""

    def test_automatic_cleanup(self, temp_document):
        """Test that workspace is automatically cleaned up."""
        workspace_dir = None

        with EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        ) as workspace:
            workspace_dir = workspace.workspace_dir
            assert workspace_dir.exists()

        # After context exit, should be cleaned up
        assert not workspace_dir.exists()

    def test_cleanup_on_exception(self, temp_document):
        """Test that workspace is cleaned up even on exception."""
        workspace_dir = None

        try:
            with EphemeralWorkspace(
                source_file=temp_document,
                thread_id="test-thread",
                message_id="msg-1"
            ) as workspace:
                workspace_dir = workspace.workspace_dir
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still be cleaned up
        assert not workspace_dir.exists()

    def test_preserve_for_debugging(self, temp_document):
        """Test preserving workspace for debugging."""
        workspace_dir = None
        ws = EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        )

        with ws as workspace:
            workspace_dir = workspace.workspace_dir
            ws.preserve_for_debugging()

        # Should NOT be cleaned up
        assert workspace_dir.exists()

        # Manual cleanup for test
        import shutil
        shutil.rmtree(workspace_dir)


class TestWorkspaceManager:
    """Test WorkspaceManager utility functions."""

    def test_cleanup_orphaned_workspaces(self, temp_document):
        """Test cleaning up orphaned workspaces."""
        # Create some old workspaces
        old_workspace = Path("/tmp/harlowe_ws_old_test_123")
        old_workspace.mkdir(exist_ok=True)

        # Clean up old workspaces (age 0 hours = all)
        count = WorkspaceManager.cleanup_orphaned_workspaces(max_age_hours=0)

        assert count >= 1
        assert not old_workspace.exists()

    def test_get_workspace_size(self, temp_document):
        """Test calculating workspace size."""
        with EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        ) as workspace:
            size = WorkspaceManager.get_workspace_size(workspace.workspace_dir)
            assert size > 0
            assert size == workspace.workspace_file.stat().st_size

    def test_get_workspace_size_nonexistent(self):
        """Test workspace size for nonexistent directory."""
        size = WorkspaceManager.get_workspace_size(Path("/tmp/nonexistent"))
        assert size == 0

    def test_list_active_workspaces(self, temp_document):
        """Test listing active workspaces."""
        with EphemeralWorkspace(
            source_file=temp_document,
            thread_id="test-thread",
            message_id="msg-1"
        ) as workspace:
            workspaces = WorkspaceManager.list_active_workspaces()
            workspace_names = [w.name for w in workspaces]
            assert any(workspace.workspace_dir.name in name for name in workspace_names)

    def test_init_workspace_cleanup(self):
        """Test initial workspace cleanup."""
        # Create a test workspace
        test_ws = Path("/tmp/harlowe_ws_init_test_456")
        test_ws.mkdir(exist_ok=True)

        # Run init cleanup
        count = WorkspaceManager.init_workspace_cleanup()

        # Should clean up all old workspaces
        assert not test_ws.exists()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_source_file(self):
        """Test handling of missing source file."""
        nonexistent = Path("/tmp/nonexistent_file.md")

        with EphemeralWorkspace(
            source_file=nonexistent,
            thread_id="test-thread",
            message_id="msg-1"
        ) as workspace:
            # Should create workspace even if source doesn't exist
            assert workspace.workspace_dir.exists()
            # But workspace file won't exist
            assert not workspace.workspace_file.exists()

    def test_concurrent_workspaces(self, temp_document):
        """Test multiple concurrent workspaces."""
        workspaces = []

        # Create multiple workspaces
        for i in range(3):
            ws = EphemeralWorkspace(
                source_file=temp_document,
                thread_id=f"thread-{i}",
                message_id=f"msg-{i}"
            )
            workspaces.append(ws)

        # Enter all contexts
        contexts = [ws.__enter__() for ws in workspaces]

        # All should exist simultaneously
        for ctx in contexts:
            assert ctx.workspace_dir.exists()

        # Exit all contexts
        for ws in workspaces:
            ws.__exit__(None, None, None)

        # All should be cleaned up
        for ctx in contexts:
            assert not ctx.workspace_dir.exists()

    def test_large_file_handling(self):
        """Test handling of larger files."""
        # Create a larger temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            # Write ~100KB of content
            for i in range(1000):
                f.write(f"Line {i}: " + "x" * 100 + "\n")
            temp_path = Path(f.name)

        try:
            with EphemeralWorkspace(
                source_file=temp_path,
                thread_id="test-thread",
                message_id="msg-1"
            ) as workspace:
                # Should handle large files
                assert workspace.workspace_file.exists()
                original_size = temp_path.stat().st_size
                workspace_size = workspace.workspace_file.stat().st_size
                assert workspace_size == original_size
        finally:
            temp_path.unlink(missing_ok=True)

    def test_workspace_changes_metadata(self, temp_document):
        """Test WorkspaceChanges metadata."""
        thread_id = "test-thread"
        message_id = "msg-1"
        ws = EphemeralWorkspace(
            source_file=temp_document,
            thread_id=thread_id,
            message_id=message_id
        )

        with ws as workspace:
            workspace.workspace_file.write_text("# Changed\n")
            changes = ws.get_changes()

        assert changes.thread_id == thread_id
        assert changes.message_id == message_id
        assert isinstance(changes.timestamp, datetime)
        assert changes.timestamp <= datetime.now()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
