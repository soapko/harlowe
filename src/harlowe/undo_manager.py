"""Undo/redo functionality using git revert with intelligent conflict resolution."""

import logging
import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from .git_manager import GitManager, GitOperationResult
from .models import CommentThread, ThreadStatus, MessageRole, Message

if TYPE_CHECKING:
    from .thread_manager_concurrent import ClaudeThreadManager


logger = logging.getLogger(__name__)


class UndoManager:
    """
    Manages undo/redo operations using git revert.

    Features:
    - Silent execution for clean undos
    - Auto-creates resolution threads for conflicts
    - Git-backed safety (full reversibility)
    - Status messages in thread chat
    """

    def __init__(
        self,
        git_manager: GitManager,
        thread_manager: 'ClaudeThreadManager'
    ):
        """
        Initialize the UndoManager.

        Args:
            git_manager: GitManager instance for version control
            thread_manager: ClaudeThreadManager for thread operations
        """
        self.git_manager = git_manager
        self.thread_manager = thread_manager

    async def undo_thread(self, thread: CommentThread) -> None:
        """
        Undo a thread's changes.
        Auto-creates resolution thread if conflicts exist.

        Args:
            thread: The thread whose changes should be undone
        """
        # Check if thread can be undone
        if not self._can_undo(thread):
            self._post_error(thread, "Cannot undo: thread not merged or already undone")
            return

        # Get git commit for this thread
        commit_hash = self._get_thread_commit(thread)
        if not commit_hash:
            self._post_error(thread, "Cannot find commit for thread")
            return

        # Test for conflicts
        has_conflicts = not self.git_manager.can_revert_cleanly(commit_hash)

        if not has_conflicts:
            # Clean undo - just do it
            await self._execute_clean_undo(thread, commit_hash)
        else:
            # Conflicts - create resolution thread
            await self._create_undo_resolution_thread(thread, commit_hash)

    async def redo_thread(self, thread: Optional[CommentThread] = None) -> None:
        """
        Redo an undone thread (revert the revert).

        Args:
            thread: Specific thread to redo. If None, redoes most recently undone thread.
        """
        # If no thread specified, find most recently undone thread
        if thread is None:
            thread = self._get_most_recent_undone_thread()
            if not thread:
                logger.warning("No undone thread to redo")
                return

        # Check if thread can be redone
        if not self._can_redo(thread):
            self._post_error(thread, "Cannot redo: thread not undone or missing revert commit")
            return

        revert_commit = thread.metadata.get('revert_commit')
        if not revert_commit:
            logger.warning(f"No revert commit found for thread {thread.id}")
            return

        # Revert the revert (restores original changes)
        redo_result = self.git_manager.revert_commit(revert_commit)

        if isinstance(redo_result, GitOperationResult):
            self._post_error(thread, f"Redo failed: {redo_result.value}")
            return

        # Update metadata
        thread.metadata['reverted'] = False
        thread.metadata['redo_commit'] = redo_result

        # Post status
        self._post_status(thread, "Changes re-applied")

        logger.info(f"Redone thread {thread.id} -> {redo_result}")

    async def _execute_clean_undo(
        self,
        thread: CommentThread,
        commit_hash: str
    ) -> None:
        """
        Execute clean undo (no conflicts).

        Args:
            thread: The thread being undone
            commit_hash: The git commit to revert
        """
        try:
            # Perform git revert
            revert_result = self.git_manager.revert_commit(commit_hash)

            if isinstance(revert_result, GitOperationResult):
                self._post_error(thread, f"Undo failed: {revert_result.value}")
                return

            # Update thread metadata
            thread.metadata['reverted'] = True
            thread.metadata['revert_commit'] = revert_result

            # Post status message
            self._post_status(thread, "Changes undone")

            logger.info(f"Undone thread {thread.id} -> {revert_result}")

        except Exception as e:
            logger.error(f"Failed to undo thread {thread.id}: {e}", exc_info=True)
            self._post_error(thread, f"Undo failed: {str(e)}")

    async def _create_undo_resolution_thread(
        self,
        thread: CommentThread,
        commit_hash: str
    ) -> CommentThread:
        """
        Create Claude thread to resolve undo conflicts.

        Args:
            thread: The thread being undone
            commit_hash: The commit that has conflicts

        Returns:
            The newly created resolution thread
        """
        # Find conflicting threads
        conflicting_threads = self._find_conflicts(thread, commit_hash)

        # Build context for Claude
        context = self._build_undo_conflict_context(
            thread,
            conflicting_threads
        )

        # Create system thread
        resolution_thread = CommentThread(
            selected_text="",
            initial_comment=f"⚙️ Undo {thread.id} - Resolution",
            line_start=0,
            line_end=0,
            status=ThreadStatus.ACTIVE
        )
        resolution_thread.metadata.update({
            'is_system_thread': True,
            'undo_target': thread.id,
            'commit_hash': commit_hash,
            'conflicts_with': [t.id for t in conflicting_threads]
        })

        # Add system message
        resolution_thread.add_message(
            MessageRole.ASSISTANT,
            "[Harlowe]: Conflict resolution thread 🤖\n\n" + context
        )

        # Add to thread manager
        self.thread_manager.threads.append(resolution_thread)

        # Post status to original thread
        conflict_thread_name = conflicting_threads[0].id if conflicting_threads else "another thread"
        self._post_status(
            thread,
            f"Conflict detected with {conflict_thread_name}. Created resolution thread"
        )

        # Notify UI of new thread
        self.thread_manager._notify_update(resolution_thread)

        logger.info(f"Created undo resolution thread {resolution_thread.id} for {thread.id}")

        return resolution_thread

    def _build_undo_conflict_context(
        self,
        target_thread: CommentThread,
        conflicting_threads: List[CommentThread]
    ) -> str:
        """
        Build prompt for Claude to resolve undo conflict.

        Args:
            target_thread: The thread being undone
            conflicting_threads: Threads that conflict with the undo

        Returns:
            Context string for Claude
        """
        if not conflicting_threads:
            return f"""
You requested to undo changes from thread {target_thread.id}.

However, there are conflicts preventing a clean undo. This likely means
other changes were made to the same sections after this thread.

Would you like me to investigate and help resolve these conflicts?
"""

        conflict_thread = conflicting_threads[0]  # For simplicity, take first

        context = f"""
You requested to undo changes from thread {target_thread.id}.

However, thread {conflict_thread.id} modified the same
sections of the document after thread {target_thread.id}.

To undo thread {target_thread.id} while preserving thread
{conflict_thread.id}'s changes, I need to carefully merge the changes.

Here's what each thread did:

Thread {target_thread.id}:
{self._summarize_thread_changes(target_thread)}

Thread {conflict_thread.id}:
{self._summarize_thread_changes(conflict_thread)}

Would you like me to:
1. Undo both threads (restore to before either made changes)
2. Keep thread {conflict_thread.id}, undo only thread {target_thread.id}
3. Something else (please describe)

What's your preference?
"""
        return context

    def _can_undo(self, thread: CommentThread) -> bool:
        """
        Check if thread can be undone.

        A thread can be undone if it has been merged (has a git commit),
        regardless of its current status (ACTIVE or COMPLETED).

        Args:
            thread: The thread to check

        Returns:
            True if thread can be undone, False otherwise
        """
        # Must have git commit (indicates thread was merged)
        if 'git_commit' not in thread.metadata:
            return False

        # Must not already be undone
        if thread.metadata.get('reverted', False):
            return False

        return True

    def _can_redo(self, thread: CommentThread) -> bool:
        """
        Check if thread can be redone.

        A thread can be redone if it has been undone (reverted) and has
        a revert commit that can be reverted.

        Args:
            thread: The thread to check

        Returns:
            True if thread can be redone, False otherwise
        """
        # Must be currently reverted
        if not thread.metadata.get('reverted', False):
            return False

        # Must have revert commit to undo
        if 'revert_commit' not in thread.metadata:
            return False

        return True

    def _get_thread_commit(self, thread: CommentThread) -> Optional[str]:
        """
        Get git commit hash for thread.

        Args:
            thread: The thread to get commit for

        Returns:
            Commit hash or None if not found
        """
        return thread.metadata.get('git_commit')

    def _find_conflicts(
        self,
        thread: CommentThread,
        commit_hash: str
    ) -> List[CommentThread]:
        """
        Find threads that conflict with reverting this thread.

        Args:
            thread: The thread being undone
            commit_hash: The commit to revert

        Returns:
            List of conflicting threads
        """
        # Get all commits after this one
        history = self.git_manager.get_history(limit=100)

        # Find the target commit's position
        target_index = None
        for i, commit_info in enumerate(history):
            if commit_info.hash.startswith(commit_hash):
                target_index = i
                break

        if target_index is None:
            return []

        # Find threads for commits after this one
        conflicting_threads = []
        for commit_info in history[:target_index]:  # Earlier commits (more recent)
            if commit_info.thread_id:
                # Find the thread
                for t in self.thread_manager.threads:
                    if str(t.id) == commit_info.thread_id:
                        conflicting_threads.append(t)
                        break

        return conflicting_threads

    def _summarize_thread_changes(self, thread: CommentThread) -> str:
        """
        Get human-readable summary of thread's changes.

        Args:
            thread: The thread to summarize

        Returns:
            Summary string
        """
        commit_hash = self._get_thread_commit(thread)
        if not commit_hash:
            return "No changes recorded"

        # Get metadata from git
        metadata = self.git_manager.get_commit_metadata(commit_hash)
        if not metadata:
            return "Unable to retrieve change details"

        message = metadata.get('message', '')
        lines = metadata.get('lines_affected', '')

        summary_parts = []
        if lines:
            summary_parts.append(f"Lines affected: {lines}")

        # Extract summary from commit message if available
        if message:
            # Get first meaningful line
            for line in message.split('\n'):
                line = line.strip()
                if line and not line.startswith('[') and not line.startswith('Lines:'):
                    summary_parts.append(f"Description: {line}")
                    break

        return '\n'.join(summary_parts) if summary_parts else "Modified the document"

    def _get_most_recent_undone_thread(self) -> Optional[CommentThread]:
        """
        Get the most recently undone thread.

        Returns:
            The most recent undone thread or None
        """
        undone_threads = [
            t for t in self.thread_manager.threads
            if t.metadata.get('reverted', False) and
               'revert_commit' in t.metadata
        ]

        if not undone_threads:
            return None

        # Sort by revert time (use most recent)
        # For now, just return the last one in the list
        return undone_threads[-1]

    def _post_status(self, thread: CommentThread, message: str) -> None:
        """
        Post status message to thread's chat.

        Args:
            thread: The thread to post to
            message: The status message
        """
        self.thread_manager.post_status(thread, message)

    def _post_error(self, thread: CommentThread, message: str) -> None:
        """
        Post error message to thread's chat.

        Args:
            thread: The thread to post to
            message: The error message
        """
        # Post error as status message with warning emoji
        self.thread_manager.post_status(thread, f"⚠️ {message}")
