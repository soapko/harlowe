"""Merge coordinator for handling concurrent thread changes."""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from .git_manager import GitManager
from .workspace_manager import WorkspaceChanges
from .models import CommentThread, ThreadStatus, MessageRole, Message


logger = logging.getLogger(__name__)


class MergeStatus(Enum):
    """Status of a pending merge."""
    PENDING = "pending"
    MERGED = "merged"
    CONFLICTED = "conflicted"
    RESOLVING = "resolving"
    FAILED = "failed"


class ConflictSeverity(Enum):
    """Severity level of conflicts."""
    MINOR = "minor"      # Adjacent lines, likely safe
    MAJOR = "major"       # Overlapping lines, needs review
    BLOCKING = "blocking" # Same lines modified


@dataclass
class LineRange:
    """Represents a range of lines in a file."""
    file_path: Path
    start_line: int
    end_line: int

    def overlaps(self, other: 'LineRange') -> bool:
        """
        Check if this range overlaps with another.

        Args:
            other: Another line range

        Returns:
            True if ranges overlap
        """
        if self.file_path != other.file_path:
            return False
        return not (self.end_line < other.start_line or
                    self.start_line > other.end_line)

    def __str__(self) -> str:
        return f"{self.file_path.name}:{self.start_line}-{self.end_line}"


@dataclass
class PendingMerge:
    """A merge waiting to be applied."""
    thread_id: str
    message_id: str
    timestamp: datetime
    changes: WorkspaceChanges
    line_ranges: List[LineRange]
    status: MergeStatus = MergeStatus.PENDING


@dataclass
class Conflict:
    """Represents a merge conflict."""
    merge_a: PendingMerge
    merge_b: PendingMerge
    conflicting_ranges: List[Tuple[LineRange, LineRange]]
    severity: ConflictSeverity


class MergeCoordinator:
    """
    Coordinates merging of concurrent thread changes.

    Handles conflict detection, auto-merging, and resolution thread creation.
    """

    def __init__(
        self,
        git_manager: GitManager,
        document_path: Path,
        thread_manager=None
    ):
        """
        Initialize the merge coordinator.

        Args:
            git_manager: Git manager for commits
            document_path: Path to the main document
            thread_manager: Thread manager (optional, for resolution threads)
        """
        self.git_manager = git_manager
        self.document_path = Path(document_path)
        self.thread_manager = thread_manager

        self.pending_merges: List[PendingMerge] = []
        self.merge_lock = asyncio.Lock()

    async def queue_merge(
        self,
        thread: CommentThread,
        changes: WorkspaceChanges
    ) -> None:
        """
        Queue thread's changes for merging.

        Attempts auto-merge or creates resolution thread for conflicts.

        Args:
            thread: The thread that generated changes
            changes: The changes to merge
        """
        async with self.merge_lock:
            try:
                # Parse changes to extract line ranges
                line_ranges = self._parse_line_ranges(changes)

                # Create pending merge
                merge = PendingMerge(
                    thread_id=str(thread.id),
                    message_id=f"msg-{len(thread.messages)}",
                    timestamp=datetime.now(),
                    changes=changes,
                    line_ranges=line_ranges,
                    status=MergeStatus.PENDING
                )

                # Check for conflicts with pending merges
                conflicts = self._detect_conflicts(merge)

                if not conflicts:
                    # No conflicts - attempt auto-merge
                    success = await self._apply_merge(merge, thread)
                    if success:
                        merge.status = MergeStatus.MERGED
                        await self._post_status(thread, "Changes merged successfully")
                        logger.info(f"Auto-merged thread {thread.id}")
                    else:
                        # Merge failed (file changed unexpectedly)
                        merge.status = MergeStatus.FAILED
                        self.pending_merges.append(merge)
                        await self._post_status(
                            thread,
                            "Merge failed - file may have changed"
                        )
                        logger.error(f"Failed to apply merge for thread {thread.id}")
                else:
                    # Conflicts detected
                    merge.status = MergeStatus.CONFLICTED
                    self.pending_merges.append(merge)

                    # Create resolution thread
                    if self.thread_manager:
                        await self._create_resolution_thread([merge] + [c.merge_b for c in conflicts])

                    conflict_info = ", ".join([str(c.merge_b.thread_id) for c in conflicts])
                    await self._post_status(
                        thread,
                        f"Conflict detected with {conflict_info}. Resolution needed."
                    )
                    logger.warning(f"Conflict detected for thread {thread.id} with {conflict_info}")

            except Exception as e:
                logger.error(f"Error queueing merge for thread {thread.id}: {e}", exc_info=True)
                await self._post_status(thread, f"Error processing changes: {str(e)}")

    def _parse_line_ranges(self, changes: WorkspaceChanges) -> List[LineRange]:
        """
        Extract line ranges from changes.

        Args:
            changes: Workspace changes with diffs

        Returns:
            List of line ranges affected by changes
        """
        ranges = []

        for file_path, file_change in changes.files_changed.items():
            diff = file_change.unified_diff

            # Parse unified diff format
            # Example: @@ -10,5 +10,7 @@
            for line in diff.split('\n'):
                if line.startswith('@@'):
                    match = re.match(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
                    if match:
                        # old_start = int(match.group(1))
                        # old_count = int(match.group(2))
                        new_start = int(match.group(3))
                        new_count = int(match.group(4))

                        # Use new range (after modification)
                        ranges.append(LineRange(
                            file_path=file_path,
                            start_line=new_start,
                            end_line=new_start + new_count
                        ))

        return ranges

    def _detect_conflicts(self, new_merge: PendingMerge) -> List[Conflict]:
        """
        Check for conflicts with existing pending merges.

        Args:
            new_merge: The new merge to check

        Returns:
            List of conflicts detected
        """
        conflicts = []

        for pending in self.pending_merges:
            if pending.status != MergeStatus.PENDING:
                continue

            conflicting_ranges = []
            for range_a in new_merge.line_ranges:
                for range_b in pending.line_ranges:
                    if range_a.overlaps(range_b):
                        conflicting_ranges.append((range_a, range_b))

            if conflicting_ranges:
                severity = self._assess_severity(conflicting_ranges)
                conflicts.append(Conflict(
                    merge_a=new_merge,
                    merge_b=pending,
                    conflicting_ranges=conflicting_ranges,
                    severity=severity
                ))

        return conflicts

    def _assess_severity(
        self,
        ranges: List[Tuple[LineRange, LineRange]]
    ) -> ConflictSeverity:
        """
        Determine how serious the conflict is.

        Args:
            ranges: List of conflicting range pairs

        Returns:
            Severity level
        """
        for range_a, range_b in ranges:
            # Exact same lines = blocking
            if (range_a.start_line == range_b.start_line and
                range_a.end_line == range_b.end_line):
                return ConflictSeverity.BLOCKING

            # Significant overlap = major
            overlap_size = (min(range_a.end_line, range_b.end_line) -
                            max(range_a.start_line, range_b.start_line))
            if overlap_size > 5:
                return ConflictSeverity.MAJOR

        # Adjacent or small overlap = minor
        return ConflictSeverity.MINOR

    async def _apply_merge(self, merge: PendingMerge, thread: CommentThread) -> bool:
        """
        Apply diff to main file.

        Args:
            merge: The merge to apply
            thread: The thread object (for storing metadata)

        Returns:
            True if successful, False otherwise
        """
        try:
            for file_path, file_change in merge.changes.files_changed.items():
                # Read current file
                if not file_path.exists():
                    logger.error(f"File not found: {file_path}")
                    return False

                original = file_path.read_text()

                # Apply unified diff
                patched = self._apply_unified_diff(original, file_change.unified_diff)

                # Verify the patch produced changes
                if patched == original:
                    logger.warning(f"Diff application produced no changes for {file_path.name}")
                    # Continue anyway - might be whitespace-only changes

                # Write patched content back to file
                file_path.write_text(patched)
                logger.info(f"Applied changes to {file_path.name}")

            # Commit to git
            files_changed = list(merge.changes.files_changed.keys())
            lines_affected = self._format_line_ranges(merge.line_ranges)

            commit_hash = self.git_manager.commit_merge(
                thread_id=merge.thread_id,
                message=f"Thread {merge.thread_id} changes",
                files_changed=files_changed,
                lines_affected=lines_affected
            )

            if commit_hash:
                # Store commit hash in thread metadata for undo functionality
                thread.metadata['git_commit'] = commit_hash
                logger.info(f"Merged {merge.thread_id} -> {commit_hash}")

                # Post status message to thread
                if self.thread_manager:
                    self.thread_manager.post_status(thread, "Merged to main")

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Failed to apply merge {merge.thread_id}: {e}", exc_info=True)
            return False

    def _apply_unified_diff(self, original: str, diff: str) -> str:
        """
        Apply unified diff to original text.

        Args:
            original: Original file content
            diff: Unified diff string

        Returns:
            Patched content
        """
        try:
            import patch
            # Use the patch library if available
            patch_set = patch.fromstring(diff.encode())
            if not patch_set:
                logger.warning("Empty patch set, returning original content")
                return original

            # Apply the patch
            result = patch.apply(patch_set, original.encode())
            return result.decode() if result else original
        except ImportError:
            # Fallback: use manual diff application
            return self._apply_diff_manual(original, diff)
        except Exception as e:
            logger.error(f"Failed to apply diff: {e}", exc_info=True)
            return original

    def _apply_diff_manual(self, original: str, diff: str) -> str:
        """
        Manually apply unified diff (fallback when patch library unavailable).

        Args:
            original: Original file content
            diff: Unified diff string

        Returns:
            Patched content
        """
        try:
            original_lines = original.splitlines(keepends=True)
            result_lines = []
            i = 0  # Current line in original

            for line in diff.split('\n'):
                if line.startswith('@@'):
                    # Parse hunk header: @@ -start,count +start,count @@
                    import re
                    match = re.match(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
                    if match:
                        old_start = int(match.group(1)) - 1  # Convert to 0-indexed
                        # Add lines before this hunk
                        while i < old_start:
                            result_lines.append(original_lines[i])
                            i += 1
                elif line.startswith('+') and not line.startswith('+++'):
                    # Added line
                    result_lines.append(line[1:] + '\n')
                elif line.startswith('-') and not line.startswith('---'):
                    # Removed line - skip it in original
                    i += 1
                elif line.startswith(' '):
                    # Context line - copy from original
                    if i < len(original_lines):
                        result_lines.append(original_lines[i])
                        i += 1

            # Add remaining lines from original
            while i < len(original_lines):
                result_lines.append(original_lines[i])
                i += 1

            return ''.join(result_lines)
        except Exception as e:
            logger.error(f"Manual diff application failed: {e}", exc_info=True)
            return original

    def _format_line_ranges(self, ranges: List[LineRange]) -> str:
        """
        Format line ranges as a string.

        Args:
            ranges: List of line ranges

        Returns:
            Formatted string like "file.md:10-20, file.md:30-35"
        """
        return ", ".join([str(r) for r in ranges])

    async def _create_resolution_thread(
        self,
        conflicted_merges: List[PendingMerge]
    ) -> Optional[CommentThread]:
        """
        Create system thread for conflict resolution.

        Args:
            conflicted_merges: List of conflicting merges

        Returns:
            The created resolution thread, or None if failed
        """
        if not self.thread_manager:
            logger.warning("Cannot create resolution thread: no thread manager")
            return None

        try:
            # Build context prompt for Claude
            context = self._build_conflict_context(conflicted_merges)

            # Create thread with initial context
            thread_id = str(uuid4())
            thread = CommentThread(
                id=thread_id,
                selected_text="[Merge Conflict Resolution]",
                initial_comment=context,
                line_start=0,
                line_end=0,
                status=ThreadStatus.ACTIVE
            )

            # Add system message
            thread.add_message(
                MessageRole.SYSTEM,
                "[Harlowe]: Conflict resolution thread 🤖"
            )
            thread.add_message(
                MessageRole.ASSISTANT,
                context
            )

            # Add to thread manager
            self.thread_manager.threads.append(thread)

            logger.info(f"Created resolution thread {thread_id}")
            return thread

        except Exception as e:
            logger.error(f"Failed to create resolution thread: {e}", exc_info=True)
            return None

    def _build_conflict_context(
        self,
        conflicted_merges: List[PendingMerge]
    ) -> str:
        """
        Build prompt for Claude to resolve conflict.

        Args:
            conflicted_merges: List of conflicting merges

        Returns:
            Context string for resolution
        """
        if len(conflicted_merges) < 2:
            return "Conflict detected but insufficient information."

        merge_a = conflicted_merges[0]
        merge_b = conflicted_merges[1]

        context = f"""I've detected conflicting changes from concurrent threads:

**Thread {merge_a.thread_id}:**
- Modified: {self._format_line_ranges(merge_a.line_ranges)}
- {merge_a.changes.total_changes} line changes

**Thread {merge_b.thread_id}:**
- Modified: {self._format_line_ranges(merge_b.line_ranges)}
- {merge_b.changes.total_changes} line changes

Both threads modified overlapping sections of the document.

Would you like me to:
1. Merge both changes intelligently (if compatible)
2. Choose one thread's changes (discard the other)
3. Help you manually merge (specify the result)

What's your preference?
"""
        return context

    async def _post_status(self, thread: CommentThread, message: str) -> None:
        """
        Post system status message to thread's chat.

        Args:
            thread: The thread to post to
            message: The status message
        """
        # Use the new system_message factory method
        status_msg = Message.system_message(message)
        thread.messages.append(status_msg)
        thread.updated_at = datetime.now()

        # Trigger UI update if thread manager available
        if self.thread_manager and self.thread_manager._on_update_callback:
            try:
                self.thread_manager._on_update_callback(thread)
            except Exception as e:
                logger.error(f"Update callback failed: {e}")

        logger.info(f"Status [{thread.id}]: {message}")

    def get_pending_count(self) -> int:
        """
        Get number of pending merges.

        Returns:
            Count of pending merges
        """
        return len([m for m in self.pending_merges if m.status == MergeStatus.PENDING])

    def clear_completed(self) -> int:
        """
        Remove completed/failed merges from queue.

        Returns:
            Number of merges removed
        """
        before = len(self.pending_merges)
        self.pending_merges = [
            m for m in self.pending_merges
            if m.status in (MergeStatus.PENDING, MergeStatus.RESOLVING)
        ]
        return before - len(self.pending_merges)
