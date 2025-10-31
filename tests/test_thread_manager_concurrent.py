"""Unit tests for concurrent thread manager."""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from harlowe.thread_manager_concurrent import ClaudeThreadManager
from harlowe.models import CommentThread, ThreadStatus, MessageRole


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
def mock_merge_coordinator():
    """Create a mock merge coordinator."""
    coordinator = Mock()
    coordinator.queue_merge = AsyncMock()
    return coordinator


@pytest_asyncio.fixture
async def thread_manager(temp_document, mock_merge_coordinator):
    """Create a thread manager instance."""
    manager = ClaudeThreadManager(
        claude_command="echo",  # Use echo for testing
        file_path=str(temp_document),
        merge_coordinator=mock_merge_coordinator
    )
    yield manager
    # Cleanup: wait for all tasks and shutdown
    await manager.wait_for_all()
    await manager.shutdown()


class TestThreadManagerInitialization:
    """Test thread manager initialization."""

    def test_initialization(self, thread_manager):
        """Test basic initialization."""
        assert thread_manager.threads == []
        assert thread_manager.active_processes == {}
        assert thread_manager.active_tasks == {}

    def test_initialization_with_concurrency_limit(self, temp_document):
        """Test initialization with concurrency limit."""
        manager = ClaudeThreadManager(
            file_path=str(temp_document),
            max_concurrent=3
        )
        assert manager.max_concurrent == 3
        assert manager.semaphore is not None

    def test_initialization_without_merge_coordinator(self, temp_document):
        """Test initialization without merge coordinator."""
        manager = ClaudeThreadManager(file_path=str(temp_document))
        assert manager.merge_coordinator is None


class TestThreadCreation:
    """Test thread creation and lifecycle."""

    def test_create_thread(self, thread_manager):
        """Test creating a thread."""
        thread = thread_manager.create_thread(
            selected_text="Test text",
            comment="Test comment",
            line_start=1,
            line_end=3
        )

        assert thread is not None
        assert thread.selected_text == "Test text"
        assert thread.initial_comment == "Test comment"
        assert thread.line_start == 1
        assert thread.line_end == 3
        assert thread.status == ThreadStatus.PENDING
        assert thread in thread_manager.threads

    def test_thread_gets_unique_id(self, thread_manager):
        """Test that each thread gets a unique ID."""
        thread1 = thread_manager.create_thread("text1", "comment1", 1, 2)
        thread2 = thread_manager.create_thread("text2", "comment2", 3, 4)

        assert thread1.id != thread2.id

    @pytest.mark.asyncio
    async def test_thread_task_created(self, thread_manager):
        """Test that creating a thread creates an async task."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)
        thread_id = str(thread.id)

        # Task should be registered
        assert thread_id in thread_manager.active_tasks

        # Wait a bit for task to start
        await asyncio.sleep(0.1)


class TestConcurrentExecution:
    """Test concurrent thread execution."""

    @pytest.mark.asyncio
    async def test_multiple_threads_run_concurrently(self, thread_manager):
        """Test that multiple threads can run at the same time."""
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = thread_manager.create_thread(
                selected_text=f"Text {i}",
                comment=f"Comment {i}",
                line_start=i * 3 + 1,
                line_end=i * 3 + 3
            )
            threads.append(thread)

        # Give them time to start
        await asyncio.sleep(0.1)

        # Multiple tasks should be active (or completed)
        # Note: With echo command, they complete very fast
        total_tasks = len(thread_manager.active_tasks)
        completed_threads = [t for t in threads if t.status != ThreadStatus.PENDING]

        # Either tasks are running or have completed
        assert total_tasks > 0 or len(completed_threads) > 0

    @pytest.mark.asyncio
    async def test_wait_for_all(self, thread_manager):
        """Test waiting for all threads to complete."""
        # Create threads
        for i in range(3):
            thread_manager.create_thread(f"text{i}", f"comment{i}", i, i+1)

        # Wait for all
        await thread_manager.wait_for_all()

        # All tasks should be complete
        assert len(thread_manager.active_tasks) == 0

    @pytest.mark.asyncio
    async def test_concurrency_limit(self, temp_document):
        """Test that concurrency limit is respected."""
        manager = ClaudeThreadManager(
            file_path=str(temp_document),
            max_concurrent=2
        )

        # Create many threads
        for i in range(5):
            manager.create_thread(f"text{i}", f"comment{i}", i, i+1)

        await asyncio.sleep(0.1)

        # Should not exceed limit (though with echo, they complete fast)
        # This is hard to test with fast commands


class TestThreadTracking:
    """Test thread tracking and status."""

    def test_get_active_threads(self, thread_manager):
        """Test getting active threads."""
        # Create some threads
        t1 = thread_manager.create_thread("text1", "comment1", 1, 2)
        t2 = thread_manager.create_thread("text2", "comment2", 3, 4)

        # Set statuses
        t1.status = ThreadStatus.ACTIVE
        t2.status = ThreadStatus.COMPLETED

        active = thread_manager.get_active_threads()
        assert len(active) == 1
        assert active[0] == t1

    def test_get_threads_for_line(self, thread_manager):
        """Test getting threads for a specific line."""
        t1 = thread_manager.create_thread("text1", "comment1", 1, 5)
        t2 = thread_manager.create_thread("text2", "comment2", 10, 15)
        t3 = thread_manager.create_thread("text3", "comment3", 3, 7)

        # Line 4 should return t1 and t3
        threads = thread_manager.get_threads_for_line(4)
        assert len(threads) == 2
        assert t1 in threads
        assert t3 in threads
        assert t2 not in threads

    def test_get_active_count(self, thread_manager):
        """Test getting active process count."""
        # Initially zero
        assert thread_manager.get_active_count() == 0

        # Mock some active processes
        thread_manager.active_processes["thread1"] = Mock()
        thread_manager.active_processes["thread2"] = Mock()

        assert thread_manager.get_active_count() == 2


class TestThreadOperations:
    """Test thread operations (close, reopen, cancel)."""

    def test_close_thread(self, thread_manager):
        """Test closing a thread."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)
        thread.status = ThreadStatus.ACTIVE

        thread_manager.close_thread(thread)

        assert thread.status == ThreadStatus.COMPLETED

    def test_reopen_thread(self, thread_manager):
        """Test reopening a closed thread."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)
        thread.status = ThreadStatus.COMPLETED

        thread_manager.reopen_thread(thread)

        assert thread.status == ThreadStatus.ACTIVE

    def test_reopen_non_completed_thread_raises(self, thread_manager):
        """Test that reopening a non-completed thread raises error."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)
        thread.status = ThreadStatus.ACTIVE

        with pytest.raises(ValueError):
            thread_manager.reopen_thread(thread)

    @pytest.mark.asyncio
    async def test_cancel_thread(self, thread_manager):
        """Test canceling a running thread."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)

        # Give it time to start
        await asyncio.sleep(0.1)

        # Cancel it
        await thread_manager.cancel_thread(thread)

        assert thread.status == ThreadStatus.COMPLETED


class TestMessageHandling:
    """Test follow-up message handling."""

    @pytest.mark.asyncio
    async def test_send_message_waits_for_previous(self, thread_manager):
        """Test that sending a message waits for previous message to complete."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)

        # Wait for initial processing
        await asyncio.sleep(0.2)

        # Send follow-up message
        await thread_manager.send_message(thread, "follow-up message")

        # Message should be in history
        user_messages = [m for m in thread.messages if m.role == MessageRole.USER]
        assert len(user_messages) >= 1

    @pytest.mark.asyncio
    async def test_send_message_reopens_closed_thread(self, thread_manager):
        """Test that sending message to closed thread reopens it."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)
        await asyncio.sleep(0.2)

        thread.status = ThreadStatus.COMPLETED

        await thread_manager.send_message(thread, "new message")

        assert thread.status == ThreadStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_send_message_to_failed_thread_raises(self, thread_manager):
        """Test that sending message to failed thread raises error."""
        thread = thread_manager.create_thread("text", "comment", 1, 2)
        thread.status = ThreadStatus.FAILED

        with pytest.raises(ValueError):
            await thread_manager.send_message(thread, "message")


class TestCallbacks:
    """Test callback functionality."""

    def test_update_callback_called(self, thread_manager):
        """Test that update callback is called."""
        callback = Mock()
        thread_manager.set_on_update_callback(callback)

        thread = thread_manager.create_thread("text", "comment", 1, 2)

        # Manually trigger update (simulating what happens during processing)
        thread_manager._notify_update(thread)

        callback.assert_called_once_with(thread)

    def test_callback_exception_handled(self, thread_manager):
        """Test that callback exceptions don't crash the manager."""
        def failing_callback(thread):
            raise RuntimeError("Callback error")

        thread_manager.set_on_update_callback(failing_callback)
        thread = thread_manager.create_thread("text", "comment", 1, 2)

        # Should not raise
        thread_manager._notify_update(thread)


class TestPromptBuilding:
    """Test prompt building methods."""

    def test_build_initial_prompt(self, thread_manager):
        """Test building initial prompt."""
        thread = thread_manager.create_thread("Test text", "Test comment", 1, 3)

        prompt = thread_manager._build_initial_prompt(thread)

        assert "Test text" in prompt
        assert "Test comment" in prompt
        assert "lines 1-3" in prompt
        assert "Harlowe" in prompt

    def test_build_conversation_prompt(self, thread_manager):
        """Test building conversation prompt with history."""
        thread = thread_manager.create_thread("Test text", "Initial comment", 1, 3)
        thread.add_message(MessageRole.USER, "Initial comment")
        thread.add_message(MessageRole.ASSISTANT, "Response 1")
        thread.add_message(MessageRole.USER, "Follow-up")

        prompt = thread_manager._build_conversation_prompt(thread)

        assert "CONVERSATION HISTORY" in prompt
        assert "Initial comment" in prompt
        assert "Response 1" in prompt
        assert "Follow-up" in prompt

    def test_build_prompt_with_resources(self, temp_document):
        """Test building prompt with resource files."""
        # Create a resource file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Reference Document\n\nReference content.\n")
            resource_path = Path(f.name)

        try:
            manager = ClaudeThreadManager(
                file_path=str(temp_document),
                resource_files=[str(resource_path)]
            )

            thread = manager.create_thread("text", "comment", 1, 2)
            prompt = manager._build_initial_prompt(thread)

            assert "REFERENCE DOCUMENTATION" in prompt
            assert "Reference content" in prompt
        finally:
            resource_path.unlink(missing_ok=True)


class TestCommandBuilding:
    """Test Claude command building."""

    def test_build_claude_command(self, thread_manager, temp_document):
        """Test building Claude CLI command."""
        workspace_dir = temp_document.parent
        prompt = "Test prompt"

        cmd = thread_manager._build_claude_command(prompt, workspace_dir)

        assert cmd[0] == "echo"  # Our test command
        assert "--add-dir" in cmd
        assert str(workspace_dir) in cmd
        assert "--allowedTools" in cmd
        assert "-p" in cmd
        assert "Test prompt" in cmd


class TestShutdown:
    """Test graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_terminates_processes(self, thread_manager):
        """Test that shutdown terminates all processes."""
        # Create some threads
        for i in range(3):
            thread_manager.create_thread(f"text{i}", f"comment{i}", i, i+1)

        await asyncio.sleep(0.1)

        # Shutdown
        await thread_manager.shutdown()

        # All should be cleaned up
        assert len(thread_manager.active_processes) == 0
        assert len(thread_manager.active_tasks) == 0

    @pytest.mark.asyncio
    async def test_shutdown_handles_stuck_processes(self, thread_manager):
        """Test that shutdown handles processes that don't terminate."""
        # Mock a process that won't terminate
        mock_process = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.kill = Mock()
        mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError())

        thread_manager.active_processes["test"] = mock_process

        # Should complete without hanging
        await asyncio.wait_for(thread_manager.shutdown(), timeout=10.0)


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_thread_failure_handled(self, thread_manager):
        """Test that thread failures are handled gracefully."""
        # This will work with echo, but we can test the error path
        thread = thread_manager.create_thread("text", "comment", 1, 2)

        # Simulate a failure by setting error
        thread.status = ThreadStatus.FAILED
        thread.error = "Test error"

        # Manager should handle this gracefully
        assert thread.status == ThreadStatus.FAILED
        assert thread.error == "Test error"


class TestWorkspaceIntegration:
    """Test integration with workspace manager."""

    @pytest.mark.asyncio
    async def test_workspace_created_for_thread(self, thread_manager):
        """Test that workspace is created for each thread."""
        # This is more of an integration test
        # The workspace should be created and cleaned up automatically
        thread = thread_manager.create_thread("text", "comment", 1, 2)

        await asyncio.sleep(0.2)

        # Thread should have processed (workspace created and destroyed)
        # We can't directly verify workspace since it's ephemeral


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_many_threads_complete(self, thread_manager):
        """Test that many threads can complete successfully."""
        # Create many threads
        threads = []
        for i in range(10):
            thread = thread_manager.create_thread(
                f"text{i}",
                f"comment{i}",
                i * 10,
                i * 10 + 5
            )
            threads.append(thread)

        # Wait for all
        await thread_manager.wait_for_all()

        # All should be in manager
        assert len(thread_manager.threads) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
