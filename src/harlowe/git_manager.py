"""Git integration layer for version control and undo functionality."""

import subprocess
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
from enum import Enum


class GitOperationResult(Enum):
    """Result status for git operations."""
    SUCCESS = "success"
    CONFLICT = "conflict"
    ERROR = "error"
    NOT_AVAILABLE = "not_available"


@dataclass
class CommitInfo:
    """Information about a git commit."""
    hash: str
    timestamp: datetime
    message: str
    thread_id: Optional[str] = None
    lines_affected: Optional[str] = None
    is_merge: bool = False
    is_revert: bool = False

    @classmethod
    def from_log_entry(cls, log_line: str) -> Optional["CommitInfo"]:
        """Parse a git log entry into CommitInfo."""
        # Expected format: hash|timestamp|message (message can be multi-line)
        try:
            parts = log_line.split("|", 2)
            if len(parts) < 3:
                return None

            hash_str, timestamp_str, message = parts
            timestamp = datetime.fromtimestamp(int(timestamp_str))

            # Parse thread metadata from commit message
            thread_id = None
            lines_affected = None
            is_merge = False
            is_revert = False

            if "harlowe: Thread" in message:
                is_merge = True
                # Extract thread ID if present
                if "Thread " in message:
                    try:
                        thread_id = message.split("Thread ")[1].split()[0]
                    except IndexError:
                        pass
                # Extract lines if present (on separate line)
                if "\nLines: " in message:
                    try:
                        lines_part = message.split("\nLines: ")[1]
                        # Get just the line range, stop at newline or end
                        lines_affected = lines_part.split("\n")[0].strip()
                    except IndexError:
                        pass

            if message.startswith("Revert "):
                is_revert = True

            return cls(
                hash=hash_str,
                timestamp=timestamp,
                message=message,
                thread_id=thread_id,
                lines_affected=lines_affected,
                is_merge=is_merge,
                is_revert=is_revert
            )
        except (ValueError, IndexError):
            return None


class GitManager:
    """
    Manages git repository operations for Harlowe.

    Provides version control, conflict detection, and undo functionality
    for all thread operations.
    """

    def __init__(self, document_path: Path):
        """
        Initialize GitManager for a document.

        Args:
            document_path: Path to the markdown document being edited
        """
        self.document_path = Path(document_path).resolve()
        self.repo_path: Optional[Path] = None
        self.git_available = self._check_git_available()
        self._harlowe_dir = self.document_path.parent / ".harlowe"

        if self.git_available:
            self.repo_path = self._find_or_init_repo()

    def _check_git_available(self) -> bool:
        """Check if git is installed and available."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _find_or_init_repo(self) -> Optional[Path]:
        """
        Find existing git repo or initialize a new one.

        Checks if document is in existing git repo. If not, creates
        a .harlowe/.git/ repo for Harlowe-specific versioning.

        Returns:
            Path to the git repository root, or None if git not available
        """
        if not self.git_available:
            return None

        # Check if document is in an existing git repo
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.document_path.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                repo_path = Path(result.stdout.strip())
                # Check if repo has uncommitted changes - we'll handle this gracefully
                return repo_path
        except subprocess.SubprocessError:
            pass

        # No existing repo, create .harlowe/.git/
        self._harlowe_dir.mkdir(exist_ok=True)

        try:
            subprocess.run(
                ["git", "init"],
                cwd=self._harlowe_dir,
                capture_output=True,
                check=True,
                timeout=10
            )

            # Configure the repo with basic settings
            subprocess.run(
                ["git", "config", "user.name", "Harlowe"],
                cwd=self._harlowe_dir,
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["git", "config", "user.email", "harlowe@local"],
                cwd=self._harlowe_dir,
                capture_output=True,
                timeout=5
            )

            return self._harlowe_dir
        except subprocess.SubprocessError:
            return None

    def ensure_repo(self) -> bool:
        """
        Ensure git repository is ready for operations.

        Returns:
            True if repo is ready, False otherwise
        """
        return self.repo_path is not None

    def _run_git_command(
        self,
        args: List[str],
        check: bool = True,
        timeout: int = 30
    ) -> subprocess.CompletedProcess:
        """
        Run a git command in the repository.

        Args:
            args: Git command arguments (without 'git' prefix)
            check: Whether to raise exception on non-zero exit
            timeout: Command timeout in seconds

        Returns:
            CompletedProcess instance with result
        """
        if not self.repo_path:
            raise RuntimeError("Git repository not available")

        return subprocess.run(
            ["git"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout
        )

    def _ensure_file_tracked(self) -> None:
        """Ensure the document file is tracked in git."""
        if not self.repo_path:
            return

        # If using .harlowe repo, need to add the document as a path outside the repo
        if self.repo_path == self._harlowe_dir:
            # For .harlowe repo, we'll copy the file into the repo for tracking
            harlowe_copy = self._harlowe_dir / self.document_path.name
            if not harlowe_copy.exists() or harlowe_copy.read_text() != self.document_path.read_text():
                harlowe_copy.write_text(self.document_path.read_text())

            self._run_git_command(["add", str(harlowe_copy)])
        else:
            # For existing repo, just add the file normally
            try:
                self._run_git_command(["add", str(self.document_path)])
            except subprocess.CalledProcessError:
                # File might be outside repo, handle gracefully
                pass

    def commit_session_start(self) -> Optional[str]:
        """
        Create a session checkpoint commit.

        Returns:
            Commit hash if successful, None otherwise
        """
        if not self.ensure_repo():
            return None

        try:
            self._ensure_file_tracked()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"harlowe: session checkpoint - {timestamp}"

            self._run_git_command(["commit", "-m", message, "--allow-empty"])

            # Get the commit hash
            result = self._run_git_command(["rev-parse", "HEAD"])
            commit_hash = result.stdout.strip()

            # Tag the commit
            tag_name = f"harlowe/session/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            try:
                self._run_git_command(["tag", tag_name], check=False)
            except subprocess.SubprocessError:
                pass  # Tag creation is optional

            return commit_hash
        except subprocess.SubprocessError:
            return None

    def commit_merge(
        self,
        thread_id: str,
        message: str,
        files_changed: Optional[List[Path]] = None,
        lines_affected: Optional[str] = None
    ) -> Optional[str]:
        """
        Commit a thread merge operation.

        Args:
            thread_id: Unique identifier for the thread
            message: Description of the changes
            files_changed: List of files that were modified
            lines_affected: String describing affected lines (e.g., "10-25")

        Returns:
            Commit hash if successful, None otherwise
        """
        if not self.ensure_repo():
            return None

        try:
            # Ensure files are tracked
            self._ensure_file_tracked()
            if files_changed:
                for file_path in files_changed:
                    try:
                        self._run_git_command(["add", str(file_path)])
                    except subprocess.CalledProcessError:
                        pass

            # Build commit message with metadata
            commit_msg = f"harlowe: Thread {thread_id} - {message}"
            if lines_affected:
                commit_msg += f"\nLines: {lines_affected}"
            commit_msg += f"\nMessage: {thread_id}"

            self._run_git_command(["commit", "-m", commit_msg, "--allow-empty"])

            # Get the commit hash
            result = self._run_git_command(["rev-parse", "HEAD"])
            return result.stdout.strip()
        except subprocess.SubprocessError:
            return None

    def can_revert_cleanly(self, commit_hash: str) -> bool:
        """
        Test if a commit can be reverted without conflicts.

        Uses git revert --no-commit to test, then aborts to leave
        working tree unchanged.

        Args:
            commit_hash: The commit hash to test reverting

        Returns:
            True if revert would be clean, False if conflicts would occur
        """
        if not self.ensure_repo():
            return False

        try:
            # Attempt a dry-run revert
            result = self._run_git_command(
                ["revert", "--no-commit", commit_hash],
                check=False
            )

            # Abort the revert to restore working tree
            self._run_git_command(["revert", "--abort"], check=False)

            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    def revert_commit(self, commit_hash: str) -> Union[str, GitOperationResult]:
        """
        Execute a git revert to undo a commit.

        Args:
            commit_hash: The commit hash to revert

        Returns:
            New commit hash if successful, or GitOperationResult error status
        """
        if not self.ensure_repo():
            return GitOperationResult.NOT_AVAILABLE

        try:
            # Attempt the revert
            result = self._run_git_command(
                ["revert", "--no-edit", commit_hash],
                check=False
            )

            if result.returncode != 0:
                # Check if it's a conflict
                if "conflict" in result.stdout.lower() or "conflict" in result.stderr.lower():
                    # Abort the failed revert
                    self._run_git_command(["revert", "--abort"], check=False)
                    return GitOperationResult.CONFLICT
                return GitOperationResult.ERROR

            # Get the new commit hash
            hash_result = self._run_git_command(["rev-parse", "HEAD"])
            return hash_result.stdout.strip()
        except subprocess.SubprocessError:
            return GitOperationResult.ERROR

    def get_commit_metadata(self, commit_hash: str) -> Optional[dict]:
        """
        Extract thread metadata from a commit.

        Args:
            commit_hash: The commit hash to query

        Returns:
            Dictionary with thread_id, lines_affected, message, etc.
        """
        if not self.ensure_repo():
            return None

        try:
            result = self._run_git_command(
                ["log", "-1", "--format=%B", commit_hash]
            )
            message = result.stdout.strip()

            metadata = {"message": message}

            # Parse thread ID
            if "Thread " in message:
                try:
                    metadata["thread_id"] = message.split("Thread ")[1].split(" ")[0]
                except IndexError:
                    pass

            # Parse lines affected
            if "Lines: " in message:
                try:
                    metadata["lines_affected"] = message.split("Lines: ")[1].split("\n")[0]
                except IndexError:
                    pass

            return metadata
        except subprocess.SubprocessError:
            return None

    def get_history(self, limit: int = 20) -> List[CommitInfo]:
        """
        Get recent commit history.

        Args:
            limit: Maximum number of commits to return

        Returns:
            List of CommitInfo objects
        """
        if not self.ensure_repo():
            return []

        try:
            # Use %B to get full commit message instead of just subject (%s)
            result = self._run_git_command([
                "log",
                f"-{limit}",
                "--format=%H|%ct|%B%x00"  # %x00 is null byte delimiter
            ])

            commits = []
            # Split by null byte to separate commits
            for entry in result.stdout.strip().split("\x00"):
                if entry.strip():
                    commit_info = CommitInfo.from_log_entry(entry.strip())
                    if commit_info:
                        commits.append(commit_info)

            return commits
        except subprocess.SubprocessError:
            return []

    def is_available(self) -> bool:
        """Check if git functionality is available."""
        return self.git_available and self.repo_path is not None
