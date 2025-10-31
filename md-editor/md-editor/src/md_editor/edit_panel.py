"""Edit panel widget for full document editing."""

from textual.containers import Vertical
from textual.widgets import TextArea, Label
from textual.message import Message


class EditPanel(Vertical):
    """Panel for editing document content with synchronized scrolling."""

    class EditCommitted(Message):
        """Message sent when edits are committed."""

        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    class EditCancelled(Message):
        """Message sent when editing is cancelled."""
        pass

    class EditorScrolled(Message):
        """Message sent when the editor is scrolled."""

        def __init__(self, line_number: int) -> None:
            self.line_number = line_number
            super().__init__()

    def __init__(self, content: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_focus = True
        self._initial_content = content
        self._suppress_scroll_events = False
        self._last_scroll_line = 0

    def compose(self):
        """Compose the edit panel."""
        yield Label("Text Editing Mode - Ctrl-J to commit, Esc to cancel")
        yield TextArea(self._initial_content, id="edit_textarea")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        # Focus the textarea when mounted
        textarea = self.query_one("#edit_textarea", TextArea)
        textarea.focus()

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "ctrl+j":
            self._commit_edits()
            event.prevent_default()
        elif event.key == "escape":
            self._cancel_edits()
            event.prevent_default()

    def on_text_area_changed(self, event) -> None:
        """Handle text area changes to track scrolling."""
        # Track scroll position changes
        textarea = self.query_one("#edit_textarea", TextArea)
        current_line = textarea.cursor_location[0] + 1  # 1-indexed

        # Check if we've scrolled to a different line
        if current_line != self._last_scroll_line:
            self._last_scroll_line = current_line

            # Emit scroll event (unless suppressed for sync)
            if not self._suppress_scroll_events:
                self.post_message(self.EditorScrolled(line_number=current_line))

    def scroll_to_line(self, line_number: int, suppress_events: bool = False) -> None:
        """
        Scroll the editor to a specific line number (1-indexed).

        Args:
            line_number: The line number to scroll to (1-indexed)
            suppress_events: If True, don't emit EditorScrolled events (for sync)
        """
        textarea = self.query_one("#edit_textarea", TextArea)

        # Convert to 0-indexed
        target_line = max(0, line_number - 1)

        # Suppress events if requested
        old_suppress = self._suppress_scroll_events
        self._suppress_scroll_events = suppress_events
        try:
            # Move cursor to the target line
            textarea.move_cursor((target_line, 0))
            self._last_scroll_line = line_number
        finally:
            self._suppress_scroll_events = old_suppress

    def _commit_edits(self) -> None:
        """Commit the current edits."""
        textarea = self.query_one("#edit_textarea", TextArea)
        content = textarea.text
        self.post_message(self.EditCommitted(content))

    def _cancel_edits(self) -> None:
        """Cancel editing without saving."""
        self.post_message(self.EditCancelled())
