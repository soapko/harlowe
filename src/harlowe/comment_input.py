"""Comment input widget for entering editing instructions."""

from textual.widgets import TextArea
from textual.message import Message


class CommentInput(TextArea):
    """Text area for entering comments/instructions."""

    class CommentSubmitted(Message):
        """Message sent when a comment is submitted."""

        def __init__(self, comment: str) -> None:
            self.comment = comment
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_focus = True

    def clear_input(self) -> None:
        """Clear the input text."""
        self.text = ""

    def on_key(self, event) -> None:
        """Handle key events."""
        # Submit on Ctrl+J only (Enter should create newlines in the text area)
        if event.key == "ctrl+j":
            self._submit_comment()
            event.prevent_default()

    def _submit_comment(self) -> None:
        """Submit the current comment."""
        comment = self.text.strip()
        if comment:
            self.post_message(self.CommentSubmitted(comment))
            self.clear_input()
