"""Unit tests for UndoManager."""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from harlowe.undo_manager import UndoManager
from harlowe.git_manager import GitManager, GitOperationResult
from harlowe.models import CommentThread, ThreadStatus, MessageRole


@pytest.fixture
def mock_git_manager():
    """Create a mock GitManager."""
    git_manager = Mock(spec=GitManager)
    git_manager.can_revert_cleanly = Mock(return_value=True)
    git_manager.revert_commit = Mock(return_value="abc123")
    git_manager.get_history = Mock(return_value=[])
    git_manager.get_commit_metadata = Mock(return_value={
        'message': 'Test commit',
        'lines_affected': '10-15'
    })
    return git_manager


@pytest.fixture
def mock_thread_manager():
    """Create a mock ClaudeThreadManager."""
    from harlowe.models import Message

    manager = Mock()
    manager.threads = []
    manager._notify_update = Mock()

    # Add post_status method that actually appends messages
    def post_status(thread, message):
        from harlowe.models import Message
        status_msg = Message.system_message(message)
        thread.messages.append(status_msg)

    manager.post_status = Mock(side_effect=post_status)
    return manager


@pytest_asyncio.fixture
async def undo_manager(mock_git_manager, mock_thread_manager):
    """Create an UndoManager instance."""
    return UndoManager(
        git_manager=mock_git_manager,
        thread_manager=mock_thread_manager
    )


class TestUndoManagerInitialization:
    """Test UndoManager initialization."""

    def test_initialization(self, undo_manager, mock_git_manager, mock_thread_manager):
        """Test basic initialization."""
        assert undo_manager.git_manager == mock_git_manager
        assert undo_manager.thread_manager == mock_thread_manager


class TestCanUndo:
    """Test _can_undo logic."""

    def test_can_undo_completed_thread_with_commit(self, undo_manager):
        """Test that completed thread with git commit can be undone."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.COMPLETED
        )
        thread.metadata['git_commit'] = "abc123"

        assert undo_manager._can_undo(thread) is True

    def test_cannot_undo_active_thread(self, undo_manager):
        """Test that active thread cannot be undone."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.ACTIVE
        )
        thread.metadata['git_commit'] = "abc123"

        assert undo_manager._can_undo(thread) is False

    def test_cannot_undo_thread_without_commit(self, undo_manager):
        """Test that thread without git commit cannot be undone."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.COMPLETED
        )

        assert undo_manager._can_undo(thread) is False

    def test_cannot_undo_already_reverted_thread(self, undo_manager):
        """Test that already undone thread cannot be undone again."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.COMPLETED
        )
        thread.metadata['git_commit'] = "abc123"
        thread.metadata['reverted'] = True

        assert undo_manager._can_undo(thread) is False


class TestCleanUndo:
    """Test clean undo execution (no conflicts)."""

    @pytest.mark.asyncio
    async def test_clean_undo_success(self, undo_manager, mock_git_manager):
        """Test executing a clean undo."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.COMPLETED
        )
        thread.metadata['git_commit'] = "abc123"

        # Mock clean revert
        mock_git_manager.can_revert_cleanly.return_value = True
        mock_git_manager.revert_commit.return_value = "revert_xyz"

        await undo_manager.undo_thread(thread)

        # Verify git operations were called
        mock_git_manager.can_revert_cleanly.assert_called_once_with("abc123")
        mock_git_manager.revert_commit.assert_called_once_with("abc123")

        # Verify thread metadata updated
        assert thread.metadata['reverted'] is True
        assert thread.metadata['revert_commit'] == "revert_xyz"

        # Verify status message was posted
        assert len(thread.messages) > 0
        assert "[Harlowe]" in thread.messages[-1].content
        assert "undone" in thread.messages[-1].content.lower()

    @pytest.mark.asyncio
    async def test_clean_undo_git_error(self, undo_manager, mock_git_manager):
        """Test clean undo when git operation fails."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.COMPLETED
        )
        thread.metadata['git_commit'] = "abc123"

        # Mock revert failure
        mock_git_manager.can_revert_cleanly.return_value = True
        mock_git_manager.revert_commit.return_value = GitOperationResult.ERROR

        await undo_manager.undo_thread(thread)

        # Verify error message was posted
        assert len(thread.messages) > 0
        assert "⚠️" in thread.messages[-1].content
        assert "failed" in thread.messages[-1].content.lower()

        # Verify thread metadata NOT updated
        assert thread.metadata.get('reverted') is None


class TestUndoWithConflicts:
    """Test undo with conflicts."""

    @pytest.mark.asyncio
    async def test_undo_with_conflicts_creates_resolution_thread(
        self,
        undo_manager,
        mock_git_manager,
        mock_thread_manager
    ):
        """Test that undo with conflicts creates a resolution thread."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.COMPLETED
        )
        thread.metadata['git_commit'] = "abc123"

        # Mock conflict detection
        mock_git_manager.can_revert_cleanly.return_value = False

        await undo_manager.undo_thread(thread)

        # Verify resolution thread was created
        assert len(mock_thread_manager.threads) == 1
        resolution_thread = mock_thread_manager.threads[0]

        assert resolution_thread.metadata.get('is_system_thread') is True
        assert resolution_thread.metadata.get('undo_target') == thread.id
        assert resolution_thread.status == ThreadStatus.ACTIVE

        # Verify conflict message was posted
        assert len(resolution_thread.messages) > 0
        assert "conflict" in resolution_thread.messages[0].content.lower()


class TestRedo:
    """Test redo functionality."""

    @pytest.mark.asyncio
    async def test_redo_reverts_the_revert(self, undo_manager, mock_git_manager, mock_thread_manager):
        """Test that redo reverts the revert commit."""
        # Create an undone thread
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2,
            status=ThreadStatus.COMPLETED
        )
        thread.metadata['git_commit'] = "abc123"
        thread.metadata['reverted'] = True
        thread.metadata['revert_commit'] = "revert_xyz"

        mock_thread_manager.threads = [thread]
        mock_git_manager.revert_commit.return_value = "redo_abc"

        await undo_manager.redo_thread()

        # Verify redo reverted the revert
        mock_git_manager.revert_commit.assert_called_once_with("revert_xyz")

        # Verify metadata updated
        assert thread.metadata['reverted'] is False
        assert thread.metadata['redo_commit'] == "redo_abc"

    @pytest.mark.asyncio
    async def test_redo_with_no_undone_threads(self, undo_manager, mock_thread_manager):
        """Test redo when no threads have been undone."""
        mock_thread_manager.threads = []

        await undo_manager.redo_thread()

        # Should complete without errors (just logs warning)


class TestConflictDetection:
    """Test conflict detection logic."""

    def test_find_conflicts_with_later_commits(self, undo_manager, mock_git_manager):
        """Test finding threads that conflict with an undo."""
        from harlowe.git_manager import CommitInfo

        # Create threads
        thread1 = CommentThread(
            selected_text="text1",
            initial_comment="comment1",
            line_start=1,
            line_end=2
        )
        thread1.id = "thread-1"
        thread1.metadata['git_commit'] = "commit1"

        thread2 = CommentThread(
            selected_text="text2",
            initial_comment="comment2",
            line_start=1,
            line_end=2
        )
        thread2.id = "thread-2"
        thread2.metadata['git_commit'] = "commit2"

        undo_manager.thread_manager.threads = [thread1, thread2]

        # Mock git history (thread2 came after thread1)
        mock_git_manager.get_history.return_value = [
            CommitInfo(
                hash="commit2",
                timestamp=datetime.now(),
                message="harlowe: Thread thread-2",
                thread_id="thread-2",
                is_merge=True
            ),
            CommitInfo(
                hash="commit1",
                timestamp=datetime.now(),
                message="harlowe: Thread thread-1",
                thread_id="thread-1",
                is_merge=True
            ),
        ]

        # Find conflicts when undoing thread1
        conflicts = undo_manager._find_conflicts(thread1, "commit1")

        # Should find thread2 as conflicting
        assert len(conflicts) == 1
        assert conflicts[0] == thread2


class TestSummarizeChanges:
    """Test change summarization."""

    def test_summarize_thread_with_metadata(self, undo_manager, mock_git_manager):
        """Test summarizing thread changes from git metadata."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2
        )
        thread.metadata['git_commit'] = "abc123"

        mock_git_manager.get_commit_metadata.return_value = {
            'message': 'Updated documentation\nLines: 10-15',
            'lines_affected': '10-15'
        }

        summary = undo_manager._summarize_thread_changes(thread)

        assert "10-15" in summary
        assert "Updated documentation" in summary

    def test_summarize_thread_without_commit(self, undo_manager):
        """Test summarizing thread without commit."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2
        )

        summary = undo_manager._summarize_thread_changes(thread)

        assert "No changes" in summary


class TestStatusMessages:
    """Test status message posting."""

    def test_post_status_message(self, undo_manager, mock_thread_manager):
        """Test posting status message to thread."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2
        )

        undo_manager._post_status(thread, "Test status")

        assert len(thread.messages) == 1
        assert "[Harlowe]" in thread.messages[0].content
        assert "Test status" in thread.messages[0].content
        assert thread.messages[0].role == MessageRole.SYSTEM
        assert thread.messages[0].is_system is True

        # Verify post_status was called on thread manager
        mock_thread_manager.post_status.assert_called_once_with(thread, "Test status")

    def test_post_error_message(self, undo_manager, mock_thread_manager):
        """Test posting error message to thread."""
        thread = CommentThread(
            selected_text="text",
            initial_comment="comment",
            line_start=1,
            line_end=2
        )

        undo_manager._post_error(thread, "Test error")

        assert len(thread.messages) == 1
        assert "⚠️" in thread.messages[0].content
        assert "Test error" in thread.messages[0].content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
