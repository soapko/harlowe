"""Concurrent Claude thread manager for interactive conversation-based editing."""

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable
from .models import CommentThread, ThreadStatus, MessageRole, Message
from .workspace_manager import EphemeralWorkspace


logger = logging.getLogger(__name__)


class ClaudeThreadManager:
    """
    Manages Claude CLI conversation threads with concurrent execution.

    Each thread represents an ongoing conversation with Claude about
    a specific text selection. Multiple threads can run simultaneously.
    """

    def __init__(
        self,
        claude_command: str = "claude",
        file_path: str = "",
        resource_files: List[str] = None,
        max_concurrent: Optional[int] = None,
        merge_coordinator = None
    ):
        """
        Initialize the thread manager.

        Args:
            claude_command: Path to Claude CLI executable
            file_path: Path to the document being edited
            resource_files: List of resource files to include
            max_concurrent: Optional limit on concurrent threads
            merge_coordinator: Coordinator for merging thread changes
        """
        self.claude_command = claude_command
        self.file_path = Path(file_path) if file_path else None
        self.resource_files = [Path(f) for f in (resource_files or [])]
        self.threads: List[CommentThread] = []
        self.max_concurrent = max_concurrent

        # Track active processes and tasks
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.active_tasks: Dict[str, asyncio.Task] = {}

        # Optional concurrency limiter
        self.semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None

        # Merge coordinator (Task #4)
        self.merge_coordinator = merge_coordinator

        # Callback for UI updates
        self._on_update_callback: Optional[Callable] = None

    def set_on_update_callback(self, callback: Callable[[CommentThread], None]) -> None:
        """Set callback to be called when a thread is updated."""
        self._on_update_callback = callback

    def create_thread(
        self,
        selected_text: str,
        comment: str,
        line_start: int,
        line_end: int
    ) -> CommentThread:
        """
        Create a new comment thread and start processing immediately.

        Args:
            selected_text: The text that was selected
            comment: User's comment/request
            line_start: Starting line number (1-indexed)
            line_end: Ending line number (1-indexed)

        Returns:
            The created thread
        """
        thread = CommentThread(
            selected_text=selected_text,
            initial_comment=comment,
            line_start=line_start,
            line_end=line_end,
            status=ThreadStatus.PENDING
        )
        self.threads.append(thread)

        # Launch processing task immediately (non-blocking)
        try:
            task = asyncio.create_task(self._process_thread(thread))
            self.active_tasks[str(thread.id)] = task
        except RuntimeError:
            # No event loop running (e.g., in tests)
            logger.warning("Cannot create thread task: no event loop")

        return thread

    async def _process_thread(self, thread: CommentThread) -> None:
        """
        Process a single thread (runs concurrently with other threads).

        Args:
            thread: The thread to process
        """
        thread_id = str(thread.id)

        try:
            # Apply concurrency limit if configured
            if self.semaphore:
                async with self.semaphore:
                    await self._do_process_thread(thread)
            else:
                await self._do_process_thread(thread)

        except Exception as e:
            thread.status = ThreadStatus.FAILED
            thread.error = f"Thread processing failed: {str(e)}"
            logger.error(f"Thread {thread_id} failed: {e}", exc_info=True)
            self._notify_update(thread)

        finally:
            # Clean up tracking
            if thread_id in self.active_tasks:
                del self.active_tasks[thread_id]
            if thread_id in self.active_processes:
                del self.active_processes[thread_id]

    async def _do_process_thread(self, thread: CommentThread) -> None:
        """
        Actually process the thread (separate for semaphore handling).

        Args:
            thread: The thread to process
        """
        thread_id = str(thread.id)
        thread.status = ThreadStatus.ACTIVE
        self._notify_update(thread)

        # Create ephemeral workspace for this thread
        workspace = EphemeralWorkspace(
            source_file=self.file_path,
            thread_id=thread_id,
            message_id=f"msg-{len(thread.messages)}",
            resource_files=self.resource_files
        )

        with workspace as ws_info:
            try:
                # Build initial prompt (use workspace file name, not original path)
                workspace_file_name = ws_info.workspace_file.name
                prompt = self._build_initial_prompt(thread, workspace_file_name)

                # Build command pointing to workspace
                cmd = self._build_claude_command(prompt, ws_info.workspace_dir)

                # Execute Claude CLI
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=ws_info.workspace_dir
                )
                self.active_processes[thread_id] = process

                # Wait for completion
                response = await self._read_response(process)

                # Remove from active processes
                if thread_id in self.active_processes:
                    del self.active_processes[thread_id]

                # Add initial messages to history
                thread.add_message(MessageRole.USER, thread.initial_comment)
                thread.add_message(MessageRole.ASSISTANT, response)

                # Capture changes from workspace
                changes = workspace.get_changes()

                # Queue changes for merging
                if self.merge_coordinator and changes.has_changes:
                    await self.merge_coordinator.queue_merge(thread, changes)
                elif changes.has_changes:
                    logger.info(f"Thread {thread_id} has {changes.total_changes} changes (no merge coordinator)")

                self._notify_update(thread)

            except Exception as e:
                # Preserve workspace for debugging on error
                workspace.preserve_for_debugging()
                raise

    async def send_message(self, thread: CommentThread, message: str) -> None:
        """
        Send a follow-up message to a thread.

        Waits for any active message in the same thread to complete first,
        ensuring serial execution per-thread.

        Args:
            thread: The thread to send message to
            message: The message content
        """
        thread_id = str(thread.id)

        # Check for FAILED status first (before waiting for tasks)
        if thread.status == ThreadStatus.FAILED:
            raise ValueError(f"Cannot send message to failed thread {thread_id}")

        # Wait for any active task in this thread to complete BEFORE reopening
        # This prevents issues when reopening a thread whose task hasn't cleaned up yet
        if thread_id in self.active_tasks:
            task = self.active_tasks[thread_id]
            # Only wait if task isn't already done
            if not task.done():
                try:
                    # Use timeout to prevent hanging on stuck tasks
                    await asyncio.wait_for(task, timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Task for thread {thread_id} timed out, cancelling")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                except Exception as e:
                    logger.warning(f"Previous task for thread {thread_id} failed: {e}")
            # Clean up task if it's done but still registered
            if thread_id in self.active_tasks:
                del self.active_tasks[thread_id]

        # Auto-reopen closed threads (now safe - old task is complete)
        if thread.status == ThreadStatus.COMPLETED:
            self.reopen_thread(thread)

        # Add user message immediately (shows in UI)
        thread.add_message(MessageRole.USER, message)
        thread.awaiting_response = True
        self._notify_update(thread)

        # Create and launch processing task
        task = asyncio.create_task(self._process_message(thread))
        self.active_tasks[thread_id] = task

    async def _process_message(self, thread: CommentThread) -> None:
        """
        Process a follow-up message in a thread.

        Args:
            thread: The thread with the new message
        """
        thread_id = str(thread.id)

        try:
            # Create workspace for this message
            workspace = EphemeralWorkspace(
                source_file=self.file_path,
                thread_id=thread_id,
                message_id=f"msg-{len(thread.messages)}",
                resource_files=self.resource_files
            )

            with workspace as ws_info:
                try:
                    # Build conversation prompt with history (use workspace file name)
                    workspace_file_name = ws_info.workspace_file.name
                    prompt = self._build_conversation_prompt(thread, workspace_file_name)

                    # Build command
                    cmd = self._build_claude_command(prompt, ws_info.workspace_dir)

                    # Execute Claude
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=ws_info.workspace_dir
                    )
                    self.active_processes[thread_id] = process

                    # Read response
                    response = await self._read_response(process)

                    # Remove from active processes
                    if thread_id in self.active_processes:
                        del self.active_processes[thread_id]

                    # Add assistant response
                    thread.add_message(MessageRole.ASSISTANT, response)
                    thread.awaiting_response = False

                    # Capture and queue changes
                    changes = workspace.get_changes()
                    if self.merge_coordinator and changes.has_changes:
                        await self.merge_coordinator.queue_merge(thread, changes)

                    self._notify_update(thread)

                except Exception as e:
                    workspace.preserve_for_debugging()
                    raise

        except Exception as e:
            thread.error = f"Failed to send message: {str(e)}"
            thread.awaiting_response = False
            logger.error(f"Message processing failed for thread {thread_id}: {e}", exc_info=True)
            self._notify_update(thread)

        finally:
            if thread_id in self.active_tasks:
                del self.active_tasks[thread_id]

    async def cancel_thread(self, thread: CommentThread) -> None:
        """
        Cancel a running thread.

        Args:
            thread: The thread to cancel
        """
        thread_id = str(thread.id)

        # Terminate process if running
        if thread_id in self.active_processes:
            process = self.active_processes[thread_id]
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            except Exception as e:
                logger.warning(f"Error terminating process for thread {thread_id}: {e}")

        # Cancel task if running
        if thread_id in self.active_tasks:
            task = self.active_tasks[thread_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        thread.status = ThreadStatus.COMPLETED
        self._notify_update(thread)

    def close_thread(self, thread: CommentThread) -> None:
        """
        Mark a thread as completed.

        Args:
            thread: The thread to close
        """
        thread.status = ThreadStatus.COMPLETED
        self._notify_update(thread)

    def reopen_thread(self, thread: CommentThread) -> None:
        """
        Reopen a closed thread to continue conversation.

        Args:
            thread: The thread to reopen
        """
        if thread.status == ThreadStatus.COMPLETED:
            thread.status = ThreadStatus.ACTIVE
            self._notify_update(thread)
        else:
            raise ValueError(f"Can only reopen COMPLETED threads, current status: {thread.status}")

    def get_threads_for_line(self, line_number: int) -> List[CommentThread]:
        """
        Get all threads that affect a specific line.

        Args:
            line_number: The line number to check

        Returns:
            List of threads affecting that line
        """
        return [
            t for t in self.threads
            if t.line_start <= line_number <= t.line_end
        ]

    def get_active_threads(self) -> List[CommentThread]:
        """
        Get all currently running threads.

        Returns:
            List of active threads
        """
        return [t for t in self.threads if t.status == ThreadStatus.ACTIVE]

    def get_active_count(self) -> int:
        """
        Get number of currently running threads.

        Returns:
            Count of active threads
        """
        return len(self.active_processes)

    async def wait_for_all(self) -> None:
        """Wait for all active threads to complete."""
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)

    async def shutdown(self) -> None:
        """Terminate all threads and clean up."""
        # Take snapshot of processes to avoid dict modification issues
        processes = list(self.active_processes.values())

        # Terminate all processes
        for process in processes:
            try:
                process.terminate()
            except Exception:
                pass

        # Wait for all processes to terminate (with timeout)
        if processes:
            wait_tasks = []
            for p in processes:
                try:
                    wait_coro = p.wait()
                    # Only add if it's a coroutine (not a Mock or other invalid object)
                    if asyncio.iscoroutine(wait_coro):
                        wait_tasks.append(wait_coro)
                except Exception:
                    pass

            if wait_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*wait_tasks, return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    # Force kill any remaining processes
                    for process in processes:
                        try:
                            process.kill()
                        except Exception:
                            pass

        # Cancel all tasks
        tasks = list(self.active_tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for task cancellation
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Clear tracking
        self.active_processes.clear()
        self.active_tasks.clear()

    def _build_conversation_prompt(self, thread: CommentThread, workspace_file_name: str) -> str:
        """Build a prompt with full conversation history for follow-up messages.

        Args:
            thread: The comment thread
            workspace_file_name: The name of the file in the workspace (e.g., "sample.md")
        """
        prompt_parts = []

        # Add resource files
        if self.resource_files:
            prompt_parts.append("REFERENCE DOCUMENTATION:")
            for resource_file in self.resource_files:
                if resource_file.exists() and resource_file.is_file():
                    try:
                        content = resource_file.read_text()
                        prompt_parts.append(f"\n--- {resource_file.name} ---")
                        prompt_parts.append(content)
                        prompt_parts.append("--- End of reference ---\n")
                    except Exception:
                        pass
            prompt_parts.append("\n")

        # Add context
        prompt_parts.append(f"""You are assisting with editing a markdown file in Harlowe, a markdown editor.

File: {workspace_file_name}
Original Selected Text (lines {thread.line_start}-{thread.line_end}):
\"\"\"
{thread.selected_text}
\"\"\"

Initial Request: {thread.initial_comment}

CONVERSATION HISTORY:""")

        # Add all messages
        for msg in thread.messages:
            role_label = "User" if msg.role == MessageRole.USER else "Assistant"
            prompt_parts.append(f"\n{role_label}: {msg.content}\n")

        # Prompt for assistant response
        prompt_parts.append("\nAssistant:")

        return "\n".join(prompt_parts)

    def _build_initial_prompt(self, thread: CommentThread, workspace_file_name: str) -> str:
        """Build the initial system prompt for a new thread.

        Args:
            thread: The comment thread
            workspace_file_name: The name of the file in the workspace (e.g., "sample.md")
        """
        prompt_parts = []

        # Add resource files as context
        if self.resource_files:
            prompt_parts.append("REFERENCE DOCUMENTATION:")
            for resource_file in self.resource_files:
                if resource_file.exists() and resource_file.is_file():
                    try:
                        content = resource_file.read_text()
                        prompt_parts.append(f"\n--- {resource_file.name} ---")
                        prompt_parts.append(content)
                        prompt_parts.append("--- End of reference ---\n")
                    except Exception:
                        pass
            prompt_parts.append("\n")

        # Add editor context and task
        prompt_parts.append(f"""You are assisting with editing a markdown file in Harlowe, a markdown editor.

File: {workspace_file_name}
Selected Text (lines {thread.line_start}-{thread.line_end}):
\"\"\"
{thread.selected_text}
\"\"\"

User Request: {thread.initial_comment}

You have access to the following tools to make changes:
- Read: View file contents
- Edit: Make precise edits to the file
- Write: Rewrite entire file (use sparingly)
- Grep/Glob: Search for content

Please make the requested changes to the file. You can ask clarifying questions if needed.
The user will be able to see your responses and continue the conversation.""")

        return "\n".join(prompt_parts)

    def _build_claude_command(self, prompt: str, workspace_dir: Path) -> List[str]:
        """
        Build the Claude CLI command with appropriate flags.

        Args:
            prompt: The prompt to send to Claude
            workspace_dir: The workspace directory for file access

        Returns:
            Command as list of strings
        """
        cmd = [self.claude_command]

        # Add workspace directory access
        cmd.extend(["--add-dir", str(workspace_dir)])

        # Allow Read, Edit, Write, Grep, Glob tools without prompting
        cmd.extend([
            "--allowedTools", "Read",
            "--allowedTools", "Edit",
            "--allowedTools", "Write",
            "--allowedTools", "Grep",
            "--allowedTools", "Glob"
        ])

        # Use -p flag to provide prompt and exit (non-interactive mode)
        cmd.extend(["-p", prompt])

        return cmd

    async def _read_response(self, process: asyncio.subprocess.Process) -> str:
        """
        Read response from Claude process.

        Args:
            process: The subprocess to read from

        Returns:
            The response text
        """
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300.0  # 5 minute timeout
            )

            # Prefer stdout, fall back to stderr if empty
            response = stdout.decode('utf-8').strip()
            if not response:
                response = stderr.decode('utf-8').strip()

            return response

        except asyncio.TimeoutError:
            return "Error: Claude response timed out"
        except Exception as e:
            return f"Error reading response: {str(e)}"

    def _notify_update(self, thread: CommentThread) -> None:
        """
        Notify callback of thread update.

        Args:
            thread: The updated thread
        """
        if self._on_update_callback:
            try:
                self._on_update_callback(thread)
            except Exception as e:
                logger.error(f"Update callback failed for thread {thread.id}: {e}")

    def post_status(self, thread: CommentThread, message: str) -> None:
        """
        Post system status message to thread's chat.

        Args:
            thread: The thread to post to
            message: The status message content (without [Harlowe] prefix or emoji)
        """
        status_msg = Message.system_message(message)
        thread.messages.append(status_msg)
        thread.updated_at = datetime.now()

        # Trigger UI update
        self._notify_update(thread)

        logger.info(f"Status [{thread.id}]: {message}")
