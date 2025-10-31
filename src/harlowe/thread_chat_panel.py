"""Chat panel for interactive Claude conversation threads."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import RichLog, TextArea, Label
from typing import Callable, Optional

from .models import CommentThread, Message, MessageRole, ThreadStatus


class ThreadChatPanel(Container):
    """
    Side panel for displaying and interacting with a Claude conversation thread.

    Shows message history in a CLI-like log format and allows user to send follow-up messages.
    Uses keyboard shortcuts: Ctrl+J to send, Ctrl+T to close thread.
    """

    CSS = """
    ThreadChatPanel {
        width: 100%;
        height: 100%;
        background: $surface;
        border-top: solid $primary;
    }

    #chat-header {
        height: 1;
        padding: 0 1;
        background: $primary;
        text-align: center;
    }

    #message-log {
        height: 1fr;
        width: 100%;
        border: solid $accent;
        padding: 0 1;
        overflow-y: auto;
    }

    #message-input {
        height: 3;
        dock: bottom;
        border-top: solid $accent;
        padding: 1;
    }
    """

    def __init__(
        self,
        thread: CommentThread,
        on_send_message: Optional[Callable] = None,
        on_close_thread: Optional[Callable] = None,
        on_reopen_thread: Optional[Callable] = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.thread = thread
        self.on_send_message_callback = on_send_message
        self.on_close_thread_callback = on_close_thread
        self.on_reopen_thread_callback = on_reopen_thread

    def compose(self) -> ComposeResult:
        """Compose the chat panel UI."""
        # Header - thread ID
        yield Label(
            f"Thread #{str(self.thread.id)[:8]}",
            id="chat-header"
        )

        # Message log (CLI-like terminal output)
        yield RichLog(id="message-log", wrap=True, highlight=True, markup=True, min_width=0)

        # Input area
        yield TextArea(
            "",
            id="message-input",
            placeholder="Type your message here...",
            soft_wrap=True
        )

    def on_mount(self) -> None:
        """Load existing messages when panel is mounted."""
        log = self.query_one("#message-log", RichLog)
        for message in self.thread.messages:
            self._write_message(log, message)

    def focus_input(self) -> None:
        """Focus the message input area."""
        text_area = self.query_one("#message-input", TextArea)
        text_area.focus()

    def _write_message(self, log: RichLog, message: Message) -> None:
        """Write a message to the log in CLI format."""
        # Check if this is a system message
        if message.is_system or message.role == MessageRole.SYSTEM:
            # System messages: lighter styling, no timestamp
            log.write(f"[dim italic]{message.content}[/]")
            log.write("")  # Blank separator
            return

        # Role emoji and name
        if message.role == MessageRole.USER:
            role = "👤 YOU"
            role_style = "bold cyan"
        else:
            role = "🤖 CLAUDE"
            role_style = "bold green"

        # Timestamp
        timestamp = message.timestamp.strftime("%H:%M:%S")

        # Write header
        log.write(f"[{role_style}]{role}[/] [dim][{timestamp}][/]")

        # Write content
        log.write(message.content)

        # Blank separator
        log.write("")

    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "ctrl+j":
            self._send_message()
            event.prevent_default()
        elif event.key == "ctrl+t":
            self._toggle_thread()
            event.prevent_default()

    def _send_message(self) -> None:
        """Send the message in the input area."""
        text_area = self.query_one("#message-input", TextArea)
        message = text_area.text.strip()

        if message and self.on_send_message_callback:
            self.on_send_message_callback(self.thread, message)
            text_area.clear()

    def _close_thread(self) -> None:
        """Close the thread."""
        if self.on_close_thread_callback:
            self.on_close_thread_callback(self.thread)

    def _toggle_thread(self) -> None:
        """Toggle thread between active and closed states."""
        if self.thread.status == ThreadStatus.ACTIVE:
            if self.on_close_thread_callback:
                self.on_close_thread_callback(self.thread)
        elif self.thread.status == ThreadStatus.COMPLETED:
            if self.on_reopen_thread_callback:
                self.on_reopen_thread_callback(self.thread)

    def add_message(self, message: Message) -> None:
        """Add a new message to the log."""
        log = self.query_one("#message-log", RichLog)
        self._write_message(log, message)

    def update_thread(self, thread: CommentThread) -> None:
        """Update the displayed thread with new data."""
        self.thread = thread

        # Clear and refresh message log
        log = self.query_one("#message-log", RichLog)
        log.clear()

        for message in thread.messages:
            self._write_message(log, message)
