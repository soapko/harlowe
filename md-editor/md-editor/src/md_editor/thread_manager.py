"""Claude thread manager for interactive conversation-based editing."""

import asyncio
import re
from pathlib import Path
from typing import List, Optional, Callable
from .models import CommentThread, ThreadStatus, MessageRole, Message


class ClaudeThreadManager:
    """
    Manages Claude CLI conversation threads for interactive editing.

    Each thread represents an ongoing conversation with Claude about
    a specific text selection. Claude has file access and can make
    edits directly using its tools.
    """

    def __init__(
        self,
        claude_command: str = "claude",
        file_path: str = "",
        resource_files: List[str] = None
    ):
        self.claude_command = claude_command
        self.file_path = file_path
        self.resource_files = resource_files or []
        self.threads: List[CommentThread] = []
        self.is_processing = False
        self._on_update_callback: Optional[Callable] = None
        self._active_process: Optional[asyncio.subprocess.Process] = None

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
        """Create a new comment thread and add it to the queue."""
        thread = CommentThread(
            selected_text=selected_text,
            initial_comment=comment,
            line_start=line_start,
            line_end=line_end,
            status=ThreadStatus.PENDING
        )
        self.threads.append(thread)

        # Start processing if not already running
        if not self.is_processing:
            try:
                asyncio.create_task(self._process_threads())
            except RuntimeError:
                # No event loop running (e.g., in tests)
                pass

        return thread

    async def _process_threads(self) -> None:
        """Process pending threads serially (one at a time)."""
        self.is_processing = True

        while True:
            # Get next pending thread
            pending = [t for t in self.threads if t.status == ThreadStatus.PENDING]
            if not pending:
                break

            thread = pending[0]
            await self._start_thread(thread)

        self.is_processing = False

    async def _start_thread(self, thread: CommentThread) -> None:
        """Start a new Claude conversation thread."""
        try:
            thread.status = ThreadStatus.ACTIVE
            self._notify_update(thread)

            # Build initial system prompt
            prompt = self._build_initial_prompt(thread)

            # Build command with file access and prompt
            cmd = self._build_claude_command(prompt)

            # Execute Claude CLI (prompt is passed as argument, not stdin)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self._active_process = process

            # Read response asynchronously
            response = await self._read_response(process)

            # Add initial messages to history
            thread.add_message(MessageRole.USER, thread.initial_comment)
            thread.add_message(MessageRole.ASSISTANT, response)

            self._notify_update(thread)

        except Exception as e:
            thread.status = ThreadStatus.FAILED
            thread.error = f"Failed to start thread: {str(e)}"
            self._notify_update(thread)

    async def send_message(self, thread: CommentThread, message: str) -> None:
        """Send a message to an active thread. Auto-reopens closed threads."""
        # Auto-reopen closed threads
        if thread.status == ThreadStatus.COMPLETED:
            self.reopen_thread(thread)
        elif thread.status != ThreadStatus.ACTIVE:
            raise ValueError(f"Thread {thread.id} is not active (status: {thread.status})")

        try:
            # Add user message immediately so it shows in UI
            thread.add_message(MessageRole.USER, message)
            thread.awaiting_response = True
            self._notify_update(thread)

            # Build a new prompt with full conversation history for context
            # (Each follow-up creates a new Claude invocation with full conversation history)
            conversation_context = self._build_conversation_prompt(thread)

            # Start a fresh Claude invocation with full context (prompt passed as argument)
            cmd = self._build_claude_command(conversation_context)

            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Read response
            response = await self._read_response(process)

            # Add assistant response and clear awaiting flag
            thread.add_message(MessageRole.ASSISTANT, response)
            thread.awaiting_response = False

            self._notify_update(thread)

        except Exception as e:
            thread.error = f"Failed to send message: {str(e)}"
            thread.awaiting_response = False
            self._notify_update(thread)

    def close_thread(self, thread: CommentThread) -> None:
        """Mark a thread as completed."""
        thread.status = ThreadStatus.COMPLETED
        self._notify_update(thread)

        # Kill active process if this is the active thread
        if self._active_process:
            try:
                self._active_process.kill()
            except:
                pass
            self._active_process = None

    def reopen_thread(self, thread: CommentThread) -> None:
        """Reopen a closed thread to continue conversation."""
        if thread.status == ThreadStatus.COMPLETED:
            thread.status = ThreadStatus.ACTIVE
            self._notify_update(thread)
        else:
            raise ValueError(f"Can only reopen COMPLETED threads, current status: {thread.status}")

    def get_threads_for_line(self, line_number: int) -> List[CommentThread]:
        """Get all threads that affect a specific line."""
        return [
            t for t in self.threads
            if t.line_start <= line_number <= t.line_end
        ]

    def get_active_threads(self) -> List[CommentThread]:
        """Get all active threads."""
        return [t for t in self.threads if t.status == ThreadStatus.ACTIVE]

    def _build_conversation_prompt(self, thread: CommentThread) -> str:
        """Build a prompt with full conversation history for follow-up messages."""
        prompt_parts = []

        # Add resource files
        if self.resource_files:
            prompt_parts.append("REFERENCE DOCUMENTATION:")
            for resource_file in self.resource_files:
                resource_path = Path(resource_file).expanduser()
                if resource_path.exists() and resource_path.is_file():
                    try:
                        with open(resource_path, 'r') as f:
                            content = f.read()
                        prompt_parts.append(f"\n--- {resource_path.name} ---")
                        prompt_parts.append(content)
                        prompt_parts.append("--- End of reference ---\n")
                    except Exception:
                        pass
            prompt_parts.append("\n")

        # Add context
        prompt_parts.append(f"""You are assisting with editing a markdown file in Harlowe, a markdown editor.

File: {self.file_path}
Original Selected Text (lines {thread.line_start}-{thread.line_end}):
\"\"\"
{thread.selected_text}
\"\"\"

Initial Request: {thread.initial_comment}

CONVERSATION HISTORY:""")

        # Add all messages (including the new user message that was just added)
        for msg in thread.messages:
            role_label = "User" if msg.role == MessageRole.USER else "Assistant"
            prompt_parts.append(f"\n{role_label}: {msg.content}\n")

        # Prompt for assistant response
        prompt_parts.append("\nAssistant:")

        return "\n".join(prompt_parts)

    def _build_initial_prompt(self, thread: CommentThread) -> str:
        """Build the initial system prompt for a new thread."""
        prompt_parts = []

        # Add resource files as context
        if self.resource_files:
            prompt_parts.append("REFERENCE DOCUMENTATION:")
            for resource_file in self.resource_files:
                resource_path = Path(resource_file).expanduser()
                if resource_path.exists() and resource_path.is_file():
                    try:
                        with open(resource_path, 'r') as f:
                            content = f.read()
                        prompt_parts.append(f"\n--- {resource_path.name} ---")
                        prompt_parts.append(content)
                        prompt_parts.append("--- End of reference ---\n")
                    except Exception:
                        pass
            prompt_parts.append("\n")

        # Add editor context and task
        prompt_parts.append(f"""You are assisting with editing a markdown file in Harlowe, a markdown editor.

File: {self.file_path}
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

    def _build_claude_command(self, prompt: str) -> List[str]:
        """Build the Claude CLI command with appropriate flags."""
        cmd = [self.claude_command]

        # Add file and resource directory access
        if self.file_path:
            file_dir = str(Path(self.file_path).parent.absolute())
            cmd.extend(["--add-dir", file_dir])

        # Add resource file directories
        for resource_file in self.resource_files:
            resource_dir = str(Path(resource_file).parent.absolute())
            if resource_dir not in cmd:
                cmd.extend(["--add-dir", resource_dir])

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
        """Read response from Claude process."""
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
        """Notify callback of thread update."""
        if self._on_update_callback:
            self._on_update_callback(thread)
