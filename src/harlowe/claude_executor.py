"""Claude CLI executor for processing edit requests."""

import asyncio
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Callable
from pathlib import Path
from enum import Enum


class EditStatus(Enum):
    """Status of an edit request."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EditRequest:
    """An edit request to be processed by Claude."""
    id: int
    selected_text: str
    comment: str
    line_start: int
    line_end: int
    status: EditStatus = EditStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class EditResult:
    """Result of an edit request."""
    request_id: int
    success: bool
    edited_text: Optional[str] = None
    error: Optional[str] = None


class ClaudeExecutor:
    """Executes Claude CLI commands for edit requests."""

    def __init__(self, claude_command: str = "claude", resource_files: List[str] = None):
        self.claude_command = claude_command
        self.resource_files = resource_files or []
        self.queue: List[EditRequest] = []
        self.next_id = 1
        self.is_processing = False
        self._on_complete_callback: Optional[Callable] = None

    def set_on_complete_callback(self, callback: Callable[[EditResult], None]) -> None:
        """Set callback to be called when an edit completes."""
        self._on_complete_callback = callback

    def add_edit_request(self, selected_text: str, comment: str, line_start: int, line_end: int) -> EditRequest:
        """Add a new edit request to the queue."""
        request = EditRequest(
            id=self.next_id,
            selected_text=selected_text,
            comment=comment,
            line_start=line_start,
            line_end=line_end
        )
        self.next_id += 1
        self.queue.append(request)

        # Start processing if not already running
        if not self.is_processing:
            try:
                asyncio.create_task(self._process_queue())
            except RuntimeError:
                # No event loop running (e.g., in tests)
                pass

        return request

    async def _process_queue(self) -> None:
        """Process the queue of edit requests serially."""
        self.is_processing = True

        while self.queue:
            # Get next pending request
            pending = [r for r in self.queue if r.status == EditStatus.PENDING]
            if not pending:
                break

            request = pending[0]
            request.status = EditStatus.IN_PROGRESS

            # Execute the request
            result = await self._execute_edit(request)

            # Update request status
            if result.success:
                request.status = EditStatus.COMPLETED
                request.result = result.edited_text
            else:
                request.status = EditStatus.FAILED
                request.error = result.error

            # Notify callback
            if self._on_complete_callback:
                self._on_complete_callback(result)

        self.is_processing = False

    async def _execute_edit(self, request: EditRequest) -> EditResult:
        """Execute a single edit request via Claude CLI."""
        try:
            # Build the prompt with resource files included
            prompt = self._build_prompt(request)

            # Build command - just claude + prompt
            cmd = [self.claude_command, prompt]

            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                edited_text = stdout.decode('utf-8').strip()
                return EditResult(
                    request_id=request.id,
                    success=True,
                    edited_text=edited_text
                )
            else:
                error_msg = stderr.decode('utf-8').strip()
                return EditResult(
                    request_id=request.id,
                    success=False,
                    error=f"Claude CLI error: {error_msg}"
                )

        except Exception as e:
            return EditResult(
                request_id=request.id,
                success=False,
                error=f"Execution error: {str(e)}"
            )

    def _build_prompt(self, request: EditRequest) -> str:
        """Build the prompt for Claude."""
        prompt_parts = []

        # Add resource files first as reference documentation
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
                    except Exception as e:
                        # Skip files that can't be read
                        pass
            prompt_parts.append("\n")

        # Add the main editing instruction
        prompt_parts.append(f"""Edit the following markdown text according to the instruction below.
Return ONLY the edited text, without any additional explanation or formatting.

ORIGINAL TEXT (lines {request.line_start}-{request.line_end}):
\"\"\"
{request.selected_text}
\"\"\"

INSTRUCTION:
{request.comment}

EDITED TEXT:""")

        return "\n".join(prompt_parts)

    def get_pending_count(self) -> int:
        """Get count of pending edit requests."""
        return len([r for r in self.queue if r.status in [EditStatus.PENDING, EditStatus.IN_PROGRESS]])

    def get_completed_edits(self) -> List[EditRequest]:
        """Get all completed edits."""
        return [r for r in self.queue if r.status == EditStatus.COMPLETED]

    def get_failed_edits(self) -> List[EditRequest]:
        """Get all failed edits."""
        return [r for r in self.queue if r.status == EditStatus.FAILED]

    def clear_completed(self) -> None:
        """Clear completed edits from queue."""
        self.queue = [r for r in self.queue if r.status != EditStatus.COMPLETED]
