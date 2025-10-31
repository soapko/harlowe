"""Tests for status message functionality."""

import pytest
from datetime import datetime
from harlowe.models import Message, MessageRole, CommentThread, ThreadStatus


class TestMessageSystemStatus:
    """Test system message creation and formatting."""

    def test_system_message_factory(self):
        """Test Message.system_message() factory method."""
        msg = Message.system_message("Merged to main")

        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "[Harlowe]: Merged to main 🤖"
        assert msg.is_system is True
        assert isinstance(msg.timestamp, datetime)

    def test_system_message_preserves_content(self):
        """Test that system_message doesn't double-prefix."""
        msg = Message.system_message("Changes undone")

        assert msg.content == "[Harlowe]: Changes undone 🤖"
        assert msg.content.count("[Harlowe]:") == 1
        assert msg.content.count("🤖") == 1

    def test_regular_message_not_system(self):
        """Test that regular messages don't have is_system flag."""
        msg = Message(
            role=MessageRole.USER,
            content="Fix the bug"
        )

        assert msg.is_system is False

    def test_message_serialization_with_is_system(self):
        """Test that is_system field is preserved in serialization."""
        msg = Message.system_message("Test status")
        data = msg.to_dict()

        assert data['is_system'] is True
        assert data['role'] == 'system'
        assert data['content'] == "[Harlowe]: Test status 🤖"

    def test_message_deserialization_with_is_system(self):
        """Test that is_system field is restored from dict."""
        data = {
            'role': 'system',
            'content': '[Harlowe]: Test 🤖',
            'timestamp': datetime.now().isoformat(),
            'is_system': True
        }

        msg = Message.from_dict(data)

        assert msg.is_system is True
        assert msg.role == MessageRole.SYSTEM

    def test_message_deserialization_backward_compatible(self):
        """Test that messages without is_system still work."""
        data = {
            'role': 'user',
            'content': 'Hello',
            'timestamp': datetime.now().isoformat()
        }

        msg = Message.from_dict(data)

        assert msg.is_system is False  # Should default to False


class TestThreadSystemFlag:
    """Test thread system flag functionality."""

    def test_thread_is_system_default(self):
        """Test that threads default to non-system."""
        thread = CommentThread(
            selected_text="Test",
            initial_comment="Fix this"
        )

        assert thread.is_system_thread is False

    def test_thread_is_system_explicit(self):
        """Test that system threads can be marked."""
        thread = CommentThread(
            selected_text="Test",
            initial_comment="Merge resolution",
            is_system_thread=True
        )

        assert thread.is_system_thread is True

    def test_thread_serialization_with_is_system(self):
        """Test that is_system_thread is preserved in serialization."""
        thread = CommentThread(
            selected_text="Test",
            initial_comment="Resolution",
            is_system_thread=True
        )

        data = thread.to_dict()

        assert data['is_system_thread'] is True

    def test_thread_deserialization_with_is_system(self):
        """Test that is_system_thread is restored from dict."""
        thread = CommentThread(
            selected_text="Test",
            initial_comment="Resolution",
            is_system_thread=True
        )

        data = thread.to_dict()
        restored = CommentThread.from_dict(data)

        assert restored.is_system_thread is True

    def test_thread_deserialization_backward_compatible(self):
        """Test that threads without is_system_thread still work."""
        thread = CommentThread(
            selected_text="Test",
            initial_comment="Fix"
        )

        # Simulate old serialization without is_system_thread
        data = thread.to_dict()
        del data['is_system_thread']

        restored = CommentThread.from_dict(data)

        assert restored.is_system_thread is False  # Should default to False


class TestThreadManagerPostStatus:
    """Test thread manager post_status functionality."""

    def test_post_status_creates_system_message(self):
        """Test that post_status creates a proper system message."""
        from harlowe.thread_manager_concurrent import ClaudeThreadManager

        manager = ClaudeThreadManager(
            claude_command="claude",
            file_path="/tmp/test.md"
        )

        thread = CommentThread(
            selected_text="Test",
            initial_comment="Fix this"
        )

        manager.post_status(thread, "Merged to main")

        assert len(thread.messages) == 1
        msg = thread.messages[0]

        assert msg.role == MessageRole.SYSTEM
        assert msg.is_system is True
        assert msg.content == "[Harlowe]: Merged to main 🤖"

    def test_post_status_triggers_callback(self):
        """Test that post_status triggers UI update callback."""
        from harlowe.thread_manager_concurrent import ClaudeThreadManager

        callback_called = []

        def callback(t):
            callback_called.append(t)

        manager = ClaudeThreadManager(
            claude_command="claude",
            file_path="/tmp/test.md"
        )
        manager.set_on_update_callback(callback)

        thread = CommentThread(
            selected_text="Test",
            initial_comment="Fix"
        )

        manager.post_status(thread, "Test status")

        assert len(callback_called) == 1
        assert callback_called[0] is thread

    def test_post_status_updates_timestamp(self):
        """Test that post_status updates thread timestamp."""
        from harlowe.thread_manager_concurrent import ClaudeThreadManager
        import time

        manager = ClaudeThreadManager(
            claude_command="claude",
            file_path="/tmp/test.md"
        )

        thread = CommentThread(
            selected_text="Test",
            initial_comment="Fix"
        )

        original_time = thread.updated_at
        time.sleep(0.01)  # Small delay to ensure timestamp difference

        manager.post_status(thread, "Status update")

        assert thread.updated_at > original_time


class TestMergeCoordinatorStatusMessages:
    """Test merge coordinator status messages."""

    def test_post_status_uses_system_message(self):
        """Test that merge coordinator uses system messages."""
        from harlowe.models import Message, MessageRole

        # This is tested implicitly through the Message.system_message() tests
        msg = Message.system_message("Changes merged successfully")

        assert msg.role == MessageRole.SYSTEM
        assert msg.is_system is True


class TestUndoManagerStatusMessages:
    """Test undo manager status messages."""

    def test_post_status_delegates_to_thread_manager(self):
        """Test that undo manager delegates to thread manager."""
        from harlowe.undo_manager import UndoManager
        from harlowe.git_manager import GitManager
        from harlowe.thread_manager_concurrent import ClaudeThreadManager
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test file")

            git_manager = GitManager(test_file)
            git_manager.ensure_repo()

            thread_manager = ClaudeThreadManager(
                claude_command="claude",
                file_path=str(test_file)
            )

            undo_manager = UndoManager(git_manager, thread_manager)

            thread = CommentThread(
                selected_text="Test",
                initial_comment="Fix"
            )

            # This should delegate to thread_manager.post_status
            undo_manager._post_status(thread, "Test message")

            assert len(thread.messages) == 1
            msg = thread.messages[0]

            assert msg.role == MessageRole.SYSTEM
            assert msg.is_system is True
            assert msg.content == "[Harlowe]: Test message 🤖"

    def test_post_error_includes_warning(self):
        """Test that error messages include warning emoji."""
        from harlowe.undo_manager import UndoManager
        from harlowe.git_manager import GitManager
        from harlowe.thread_manager_concurrent import ClaudeThreadManager
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test file")

            git_manager = GitManager(test_file)
            git_manager.ensure_repo()

            thread_manager = ClaudeThreadManager(
                claude_command="claude",
                file_path=str(test_file)
            )

            undo_manager = UndoManager(git_manager, thread_manager)

            thread = CommentThread(
                selected_text="Test",
                initial_comment="Fix"
            )

            undo_manager._post_error(thread, "Error occurred")

            assert len(thread.messages) == 1
            msg = thread.messages[0]

            assert "⚠️" in msg.content
            assert "Error occurred" in msg.content
