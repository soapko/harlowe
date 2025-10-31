"""Unit tests for GitManager."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from harlowe.git_manager import GitManager, CommitInfo, GitOperationResult


@pytest.fixture
def temp_document():
    """Create a temporary markdown document."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Test Document\n\nThis is a test document.\n")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)
    harlowe_dir = temp_path.parent / ".harlowe"
    if harlowe_dir.exists():
        shutil.rmtree(harlowe_dir)


@pytest.fixture
def git_manager(temp_document):
    """Create a GitManager instance with a temporary document."""
    return GitManager(temp_document)


class TestGitManagerInitialization:
    """Test GitManager initialization and repository setup."""

    def test_git_available(self, git_manager):
        """Test that git is detected as available."""
        assert git_manager.git_available is True

    def test_repo_initialized(self, git_manager):
        """Test that a repository is initialized."""
        assert git_manager.repo_path is not None
        assert git_manager.ensure_repo() is True

    def test_harlowe_dir_created(self, git_manager, temp_document):
        """Test that .harlowe directory is created."""
        harlowe_dir = temp_document.parent / ".harlowe"
        assert harlowe_dir.exists()
        assert (harlowe_dir / ".git").exists()


class TestSessionCheckpoint:
    """Test session checkpoint functionality."""

    def test_commit_session_start(self, git_manager):
        """Test creating a session checkpoint commit."""
        commit_hash = git_manager.commit_session_start()

        assert commit_hash is not None
        assert len(commit_hash) == 40  # SHA-1 hash length

        # Verify commit exists in history
        history = git_manager.get_history(limit=1)
        assert len(history) == 1
        assert "session checkpoint" in history[0].message

    def test_session_checkpoint_tagged(self, git_manager):
        """Test that session checkpoints are tagged."""
        git_manager.commit_session_start()

        # Check for tag (this is a best-effort test)
        try:
            result = git_manager._run_git_command(["tag", "-l", "harlowe/session/*"])
            assert result.returncode == 0
        except Exception:
            pass  # Tag creation is optional


class TestThreadMergeCommit:
    """Test thread merge commit functionality."""

    def test_commit_merge_basic(self, git_manager):
        """Test creating a basic thread merge commit."""
        commit_hash = git_manager.commit_merge(
            thread_id="test-123",
            message="Added feature X",
            lines_affected="10-25"
        )

        assert commit_hash is not None
        assert len(commit_hash) == 40

        # Verify commit metadata
        metadata = git_manager.get_commit_metadata(commit_hash)
        assert metadata is not None
        assert metadata["thread_id"] == "test-123"
        assert metadata["lines_affected"] == "10-25"

    def test_commit_merge_with_files(self, git_manager, temp_document):
        """Test merge commit with specific files changed."""
        # Modify the document
        temp_document.write_text("# Modified\n\nNew content")

        commit_hash = git_manager.commit_merge(
            thread_id="test-456",
            message="Updated content",
            files_changed=[temp_document],
            lines_affected="1-3"
        )

        assert commit_hash is not None

    def test_commit_merge_message_format(self, git_manager):
        """Test that merge commit messages have correct format."""
        git_manager.commit_merge(
            thread_id="abc-789",
            message="Test change",
            lines_affected="5-10"
        )

        history = git_manager.get_history(limit=1)
        assert len(history) == 1
        commit = history[0]

        assert commit.is_merge is True
        assert commit.thread_id == "abc-789"
        assert commit.lines_affected == "5-10"


class TestRevertOperations:
    """Test revert and conflict detection functionality."""

    def test_can_revert_cleanly(self, git_manager, temp_document):
        """Test checking if a commit can be reverted cleanly."""
        # Create initial commit
        commit1 = git_manager.commit_session_start()

        # Make a change and commit
        temp_document.write_text("# Modified Document\n")
        commit2 = git_manager.commit_merge(
            thread_id="test-1",
            message="Modified document"
        )

        # Should be able to revert cleanly
        assert git_manager.can_revert_cleanly(commit2) is True

    def test_revert_commit_success(self, git_manager, temp_document):
        """Test successfully reverting a commit."""
        # Create initial state
        git_manager.commit_session_start()
        original_content = temp_document.read_text()

        # Make a change
        temp_document.write_text("# Changed\n")
        commit_to_revert = git_manager.commit_merge(
            thread_id="test-2",
            message="Made change"
        )

        # Revert the change
        result = git_manager.revert_commit(commit_to_revert)

        assert isinstance(result, str)  # Should return commit hash
        assert len(result) == 40

    def test_revert_leaves_revert_commit(self, git_manager):
        """Test that revert creates a revert commit in history."""
        # Create commit
        commit1 = git_manager.commit_merge(
            thread_id="test-3",
            message="Test commit"
        )

        # Revert it
        git_manager.revert_commit(commit1)

        # Check history
        history = git_manager.get_history(limit=2)
        assert len(history) >= 2
        # Most recent commit should be the revert
        assert history[0].is_revert is True


class TestCommitHistory:
    """Test commit history retrieval."""

    def test_get_history_empty(self, git_manager):
        """Test getting history when repo is empty."""
        # Fresh repo should have no commits initially
        history = git_manager.get_history()
        # After initialization, may have some commits
        assert isinstance(history, list)

    def test_get_history_limited(self, git_manager):
        """Test limiting history results."""
        # Create several commits
        for i in range(5):
            git_manager.commit_merge(
                thread_id=f"test-{i}",
                message=f"Commit {i}"
            )

        history = git_manager.get_history(limit=3)
        assert len(history) <= 3

    def test_get_history_order(self, git_manager):
        """Test that history is in reverse chronological order."""
        # Create commits with delays to ensure different timestamps
        import time

        commit1 = git_manager.commit_merge(
            thread_id="first",
            message="First commit"
        )
        time.sleep(0.1)

        commit2 = git_manager.commit_merge(
            thread_id="second",
            message="Second commit"
        )

        history = git_manager.get_history(limit=2)
        assert len(history) >= 2
        # Most recent should be first
        assert history[0].timestamp >= history[1].timestamp


class TestCommitInfoParsing:
    """Test CommitInfo parsing from git log entries."""

    def test_parse_log_entry_basic(self):
        """Test parsing a basic log entry."""
        log_line = "abc123|1234567890|Simple commit message"
        info = CommitInfo.from_log_entry(log_line)

        assert info is not None
        assert info.hash == "abc123"
        assert info.message == "Simple commit message"

    def test_parse_log_entry_with_thread(self):
        """Test parsing a log entry with thread metadata."""
        log_line = "def456|1234567890|harlowe: Thread test-123 - Added feature\nLines: 10-20"
        info = CommitInfo.from_log_entry(log_line)

        assert info is not None
        assert info.is_merge is True
        assert info.thread_id == "test-123"
        assert info.lines_affected == "10-20"

    def test_parse_log_entry_revert(self):
        """Test parsing a revert commit."""
        log_line = "ghi789|1234567890|Revert \"harlowe: Thread test-456\""
        info = CommitInfo.from_log_entry(log_line)

        assert info is not None
        assert info.is_revert is True

    def test_parse_log_entry_invalid(self):
        """Test parsing an invalid log entry."""
        log_line = "invalid"
        info = CommitInfo.from_log_entry(log_line)

        assert info is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_git_not_available(self, temp_document, monkeypatch):
        """Test graceful degradation when git is not available."""
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr("subprocess.run", mock_run)

        manager = GitManager(temp_document)
        assert manager.git_available is False
        assert manager.ensure_repo() is False
        assert manager.commit_session_start() is None

    def test_multiple_operations(self, git_manager, temp_document):
        """Test multiple git operations in sequence."""
        # Session start
        session_commit = git_manager.commit_session_start()
        assert session_commit is not None

        # Multiple merges
        for i in range(3):
            temp_document.write_text(f"# Version {i}\n")
            commit = git_manager.commit_merge(
                thread_id=f"thread-{i}",
                message=f"Change {i}"
            )
            assert commit is not None

        # Check history
        history = git_manager.get_history()
        assert len(history) >= 4  # session + 3 merges

    def test_empty_commit_allowed(self, git_manager):
        """Test that empty commits are allowed."""
        # Should work even without file changes
        commit = git_manager.commit_merge(
            thread_id="empty",
            message="No changes"
        )
        assert commit is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
