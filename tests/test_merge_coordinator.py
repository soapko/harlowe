"""Unit tests for MergeCoordinator."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from harlowe.merge_coordinator import (
    MergeCoordinator,
    LineRange,
    PendingMerge,
    Conflict,
    MergeStatus,
    ConflictSeverity
)
from harlowe.workspace_manager import WorkspaceChanges, FileChange
from harlowe.git_manager import GitManager
from harlowe.models import CommentThread


@pytest.fixture
def temp_document():
    """Create a temporary markdown document."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        content = "\n".join([f"Line {i}" for i in range(1, 101)])
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)
    harlowe_dir = temp_path.parent / ".harlowe"
    if harlowe_dir.exists():
        import shutil
        shutil.rmtree(harlowe_dir)


@pytest.fixture
def git_manager(temp_document):
    """Create a GitManager instance."""
    return GitManager(temp_document)


@pytest.fixture
def mock_thread_manager():
    """Create a mock thread manager."""
    manager = Mock()
    manager.threads = []
    manager._on_update_callback = None
    return manager


@pytest.fixture
def merge_coordinator(git_manager, temp_document, mock_thread_manager):
    """Create a MergeCoordinator instance."""
    return MergeCoordinator(
        git_manager=git_manager,
        document_path=temp_document,
        thread_manager=mock_thread_manager
    )


class TestLineRange:
    """Test LineRange functionality."""

    def test_line_range_creation(self):
        """Test creating a line range."""
        range = LineRange(
            file_path=Path("test.md"),
            start_line=10,
            end_line=20
        )
        assert range.start_line == 10
        assert range.end_line == 20

    def test_line_range_overlaps(self):
        """Test detecting overlapping ranges."""
        range1 = LineRange(Path("test.md"), 10, 20)
        range2 = LineRange(Path("test.md"), 15, 25)
        range3 = LineRange(Path("test.md"), 30, 40)

        assert range1.overlaps(range2)
        assert range2.overlaps(range1)
        assert not range1.overlaps(range3)

    def test_line_range_adjacent_not_overlapping(self):
        """Test that adjacent ranges don't overlap."""
        range1 = LineRange(Path("test.md"), 10, 20)
        range2 = LineRange(Path("test.md"), 21, 30)

        assert not range1.overlaps(range2)

    def test_line_range_different_files(self):
        """Test that ranges in different files don't overlap."""
        range1 = LineRange(Path("file1.md"), 10, 20)
        range2 = LineRange(Path("file2.md"), 10, 20)

        assert not range1.overlaps(range2)

    def test_line_range_str(self):
        """Test string representation."""
        range = LineRange(Path("test.md"), 10, 20)
        assert "test.md" in str(range)
        assert "10" in str(range)
        assert "20" in str(range)


class TestConflictDetection:
    """Test conflict detection logic."""

    def test_no_conflicts_non_overlapping(self, merge_coordinator, temp_document):
        """Test that non-overlapping changes don't conflict."""
        # Create two merges with non-overlapping ranges
        merge1 = PendingMerge(
            thread_id="thread1",
            message_id="msg1",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread1", "msg1", datetime.now()),
            line_ranges=[LineRange(temp_document, 10, 20)],
            status=MergeStatus.PENDING
        )

        merge2 = PendingMerge(
            thread_id="thread2",
            message_id="msg2",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread2", "msg2", datetime.now()),
            line_ranges=[LineRange(temp_document, 30, 40)],
            status=MergeStatus.PENDING
        )

        merge_coordinator.pending_merges.append(merge1)
        conflicts = merge_coordinator._detect_conflicts(merge2)

        assert len(conflicts) == 0

    def test_conflicts_overlapping(self, merge_coordinator, temp_document):
        """Test that overlapping changes create conflicts."""
        merge1 = PendingMerge(
            thread_id="thread1",
            message_id="msg1",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread1", "msg1", datetime.now()),
            line_ranges=[LineRange(temp_document, 10, 20)],
            status=MergeStatus.PENDING
        )

        merge2 = PendingMerge(
            thread_id="thread2",
            message_id="msg2",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread2", "msg2", datetime.now()),
            line_ranges=[LineRange(temp_document, 15, 25)],
            status=MergeStatus.PENDING
        )

        merge_coordinator.pending_merges.append(merge1)
        conflicts = merge_coordinator._detect_conflicts(merge2)

        assert len(conflicts) == 1
        assert conflicts[0].merge_a == merge2
        assert conflicts[0].merge_b == merge1


class TestSeverityAssessment:
    """Test conflict severity assessment."""

    def test_blocking_severity_same_lines(self, merge_coordinator, temp_document):
        """Test blocking severity for identical line ranges."""
        range1 = LineRange(temp_document, 10, 20)
        range2 = LineRange(temp_document, 10, 20)

        severity = merge_coordinator._assess_severity([(range1, range2)])

        assert severity == ConflictSeverity.BLOCKING

    def test_major_severity_large_overlap(self, merge_coordinator, temp_document):
        """Test major severity for large overlaps."""
        range1 = LineRange(temp_document, 10, 20)
        range2 = LineRange(temp_document, 12, 22)

        severity = merge_coordinator._assess_severity([(range1, range2)])

        assert severity == ConflictSeverity.MAJOR

    def test_minor_severity_small_overlap(self, merge_coordinator, temp_document):
        """Test minor severity for small overlaps."""
        range1 = LineRange(temp_document, 10, 15)
        range2 = LineRange(temp_document, 14, 20)

        severity = merge_coordinator._assess_severity([(range1, range2)])

        assert severity == ConflictSeverity.MINOR


class TestLineRangeParsing:
    """Test parsing line ranges from diffs."""

    def test_parse_simple_diff(self, merge_coordinator, temp_document):
        """Test parsing a simple unified diff."""
        file_change = FileChange(
            file_path=temp_document,
            unified_diff="@@ -10,5 +10,7 @@\n-old line\n+new line 1\n+new line 2",
            original_checksum="abc123",
            new_checksum="def456",
            lines_added=2,
            lines_removed=1
        )

        changes = WorkspaceChanges("thread1", "msg1", datetime.now())
        changes.files_changed[temp_document] = file_change

        ranges = merge_coordinator._parse_line_ranges(changes)

        assert len(ranges) == 1
        assert ranges[0].start_line == 10
        assert ranges[0].end_line == 17  # 10 + 7

    def test_parse_multiple_hunks(self, merge_coordinator, temp_document):
        """Test parsing diff with multiple hunks."""
        diff = "@@ -10,5 +10,7 @@\n-old\n+new\n@@ -20,3 +22,5 @@\n-old2\n+new2"
        file_change = FileChange(
            file_path=temp_document,
            unified_diff=diff,
            original_checksum="abc",
            new_checksum="def"
        )

        changes = WorkspaceChanges("thread1", "msg1", datetime.now())
        changes.files_changed[temp_document] = file_change

        ranges = merge_coordinator._parse_line_ranges(changes)

        assert len(ranges) == 2


class TestMergeQueuing:
    """Test merge queuing functionality."""

    @pytest.mark.asyncio
    async def test_queue_merge_no_conflicts(self, merge_coordinator, temp_document):
        """Test queuing a merge with no conflicts."""
        thread = CommentThread(
            selected_text="test",
            initial_comment="comment",
            line_start=1,
            line_end=5
        )

        changes = WorkspaceChanges("thread1", "msg1", datetime.now())
        # No actual changes

        await merge_coordinator.queue_merge(thread, changes)

        # Should not add to pending (no file changes)
        assert len(merge_coordinator.pending_merges) == 0

    @pytest.mark.asyncio
    async def test_queue_merge_with_conflicts(self, merge_coordinator, temp_document):
        """Test queuing a merge that conflicts."""
        # First merge
        merge1 = PendingMerge(
            thread_id="thread1",
            message_id="msg1",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread1", "msg1", datetime.now()),
            line_ranges=[LineRange(temp_document, 10, 20)],
            status=MergeStatus.PENDING
        )
        merge_coordinator.pending_merges.append(merge1)

        # Second merge that conflicts
        thread2 = CommentThread(
            selected_text="test",
            initial_comment="comment",
            line_start=15,
            line_end=25
        )

        file_change = FileChange(
            file_path=temp_document,
            unified_diff="@@ -15,5 +15,7 @@\n-old\n+new",
            original_checksum="abc",
            new_checksum="def"
        )
        changes2 = WorkspaceChanges("thread2", "msg2", datetime.now())
        changes2.files_changed[temp_document] = file_change

        await merge_coordinator.queue_merge(thread2, changes2)

        # Should add to pending with CONFLICTED status
        conflicted = [m for m in merge_coordinator.pending_merges if m.status == MergeStatus.CONFLICTED]
        assert len(conflicted) >= 1


class TestFormatting:
    """Test formatting helpers."""

    def test_format_line_ranges(self, merge_coordinator, temp_document):
        """Test formatting line ranges."""
        ranges = [
            LineRange(temp_document, 10, 20),
            LineRange(temp_document, 30, 40)
        ]

        formatted = merge_coordinator._format_line_ranges(ranges)

        assert "10" in formatted
        assert "20" in formatted
        assert "30" in formatted
        assert "40" in formatted


class TestPendingMergeManagement:
    """Test pending merge management."""

    def test_get_pending_count(self, merge_coordinator, temp_document):
        """Test getting pending merge count."""
        merge1 = PendingMerge(
            thread_id="thread1",
            message_id="msg1",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread1", "msg1", datetime.now()),
            line_ranges=[],
            status=MergeStatus.PENDING
        )
        merge2 = PendingMerge(
            thread_id="thread2",
            message_id="msg2",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread2", "msg2", datetime.now()),
            line_ranges=[],
            status=MergeStatus.MERGED
        )

        merge_coordinator.pending_merges.extend([merge1, merge2])

        assert merge_coordinator.get_pending_count() == 1

    def test_clear_completed(self, merge_coordinator, temp_document):
        """Test clearing completed merges."""
        merge1 = PendingMerge(
            thread_id="thread1",
            message_id="msg1",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread1", "msg1", datetime.now()),
            line_ranges=[],
            status=MergeStatus.MERGED
        )
        merge2 = PendingMerge(
            thread_id="thread2",
            message_id="msg2",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread2", "msg2", datetime.now()),
            line_ranges=[],
            status=MergeStatus.PENDING
        )

        merge_coordinator.pending_merges.extend([merge1, merge2])

        cleared = merge_coordinator.clear_completed()

        assert cleared == 1
        assert len(merge_coordinator.pending_merges) == 1
        assert merge_coordinator.pending_merges[0].status == MergeStatus.PENDING


class TestConflictContext:
    """Test conflict context building."""

    def test_build_conflict_context(self, merge_coordinator, temp_document):
        """Test building context for conflict resolution."""
        merge1 = PendingMerge(
            thread_id="thread1",
            message_id="msg1",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread1", "msg1", datetime.now()),
            line_ranges=[LineRange(temp_document, 10, 20)],
            status=MergeStatus.PENDING
        )
        merge2 = PendingMerge(
            thread_id="thread2",
            message_id="msg2",
            timestamp=datetime.now(),
            changes=WorkspaceChanges("thread2", "msg2", datetime.now()),
            line_ranges=[LineRange(temp_document, 15, 25)],
            status=MergeStatus.PENDING
        )

        context = merge_coordinator._build_conflict_context([merge1, merge2])

        assert "thread1" in context
        assert "thread2" in context
        assert "conflicting" in context.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
