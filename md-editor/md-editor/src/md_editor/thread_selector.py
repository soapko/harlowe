"""Thread selector widget for browsing and selecting active threads."""

from typing import List, Callable, Optional
from textual.widget import Widget
from textual.widgets import Static
from textual.scroll_view import ScrollView
from textual.message import Message
from textual.reactive import reactive
from textual.geometry import Size
from textual.strip import Strip
from rich.text import Text
from rich.style import Style

from .models import CommentThread, ThreadStatus, ThreadViewMode


class ThreadSelector(ScrollView):
    """Widget for selecting threads from a list."""

    selected_index = reactive(0)
    current_view = reactive(ThreadViewMode.ACTIVE)
    can_focus = True

    @property
    def virtual_size(self) -> Size:
        """Return the virtual size for scrolling."""
        width = self.size.width
        height = len(self.threads) if self.threads else 1
        return Size(width, height)

    class ThreadSelected(Message):
        """Message sent when a thread is selected."""

        def __init__(self, thread: CommentThread, index: int) -> None:
            self.thread = thread
            self.index = index
            super().__init__()

    class ViewChanged(Message):
        """Message sent when the view mode changes."""

        def __init__(self, view: ThreadViewMode) -> None:
            self.view = view
            super().__init__()

    def __init__(self, threads: List[CommentThread], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.all_threads = threads  # Store all threads
        self.threads = []  # Filtered threads based on current view
        self.selected_index = 0 if threads else -1

        # Disable horizontal scrolling
        self.show_horizontal_scrollbar = False

        self._apply_view_filter()  # Apply initial filter

    def update_threads(self, threads: List[CommentThread]) -> None:
        """Update the list of threads (legacy method for compatibility)."""
        self.threads = threads
        if not threads:
            self.selected_index = -1
        elif self.selected_index >= len(threads):
            self.selected_index = max(0, len(threads) - 1)
        self.refresh()

    def set_all_threads(self, threads: List[CommentThread]) -> None:
        """Store all threads and filter based on current view."""
        self.all_threads = threads
        self._apply_view_filter()

    def _apply_view_filter(self) -> None:
        """Filter and sort threads based on current view mode."""
        if self.current_view == ThreadViewMode.ACTIVE:
            filtered = [t for t in self.all_threads if t.status == ThreadStatus.ACTIVE]
        elif self.current_view == ThreadViewMode.CLOSED:
            filtered = [t for t in self.all_threads if t.status == ThreadStatus.COMPLETED]
        else:  # RECENT
            filtered = sorted(self.all_threads, key=lambda t: t.updated_at, reverse=True)

        self.threads = filtered
        self.selected_index = 0 if filtered else -1
        self.refresh()

        # Scroll to top when switching views (since we reset to index 0)
        if filtered:
            self.scroll_to(y=0, animate=False)

    def cycle_view(self, direction: int) -> None:
        """Cycle through views. direction: 1 for right, -1 for left."""
        views = [ThreadViewMode.ACTIVE, ThreadViewMode.RECENT, ThreadViewMode.CLOSED]
        current_idx = views.index(self.current_view)
        new_idx = (current_idx + direction) % len(views)  # Wraps around
        self.current_view = views[new_idx]
        self._apply_view_filter()
        self.post_message(self.ViewChanged(self.current_view))

    def render_line(self, y: int) -> Strip:
        """Render a single line of the thread list."""
        scroll_x, scroll_y = self.scroll_offset
        line_index = scroll_y + y

        # If no threads, show empty message
        if not self.threads:
            if y == 0:
                empty_msg = {
                    ThreadViewMode.ACTIVE: "No active threads",
                    ThreadViewMode.CLOSED: "No closed threads",
                    ThreadViewMode.RECENT: "No threads"
                }
                text = Text(empty_msg[self.current_view], style=Style(dim=True, italic=True))
                return Strip(text.render(self.app.console))
            else:
                return Strip.blank(self.size.width)

        # If beyond content, return blank
        if line_index >= len(self.threads):
            return Strip.blank(self.size.width)

        # Get the thread for this line
        thread = self.threads[line_index]

        # Format line numbers
        if thread.line_start == thread.line_end:
            line_info = f"L{thread.line_start}"
        else:
            line_info = f"L{thread.line_start}-{thread.line_end}"

        # Message count
        msg_count = len(thread.messages)
        msg_info = f"({msg_count})"

        # Truncate initial comment to one line (max 30 chars)
        comment_preview = thread.initial_comment[:30]
        if len(thread.initial_comment) > 30:
            comment_preview += "..."

        # Check if thread has unread updates or is awaiting response
        is_unread = thread.has_unread_updates
        is_awaiting = thread.awaiting_response

        # Add status indicator: awaiting takes priority over unread
        if is_awaiting:
            status_prefix = "⏳ "
        elif is_unread:
            status_prefix = "* "
        else:
            status_prefix = "  "

        # Build line
        line_text = f"{line_info} {msg_info} {comment_preview}"

        # Calculate available width and truncate if needed
        prefix = "> " if line_index == self.selected_index else "  "
        max_width = self.size.width - len(prefix) - len(status_prefix) - 1  # -1 for safety margin

        if len(line_text) > max_width:
            line_text = line_text[:max_width-3] + "..."

        # Combine prefix and status indicator
        full_prefix = prefix + status_prefix

        # Highlight selected
        if line_index == self.selected_index:
            text = Text(f"{full_prefix}{line_text}", style=Style(bgcolor="blue", color="white", bold=True))
        elif is_awaiting:
            # Awaiting response: cyan color to indicate activity
            text = Text(f"{full_prefix}{line_text}", style=Style(color="cyan", bold=True))
        elif is_unread:
            # Unread threads: bold and bright color
            text = Text(f"{full_prefix}{line_text}", style=Style(color="yellow", bold=True))
        else:
            text = Text(f"{full_prefix}{line_text}")

        return Strip(text.render(self.app.console))

    def move_selection(self, delta: int) -> None:
        """Move selection by delta positions."""
        if not self.threads:
            return

        new_index = self.selected_index + delta
        self.selected_index = max(0, min(new_index, len(self.threads) - 1))
        self.refresh()

        # Scroll to keep selected item visible
        self._scroll_to_selected()

        # Emit selection event
        if 0 <= self.selected_index < len(self.threads):
            self.post_message(
                self.ThreadSelected(
                    thread=self.threads[self.selected_index],
                    index=self.selected_index
                )
            )

    def _scroll_to_selected(self) -> None:
        """Scroll to make the selected thread visible."""
        if not self.threads or self.selected_index < 0:
            return

        # Each thread takes 1 line (plus newlines between them)
        # Calculate approximate scroll position
        line_height = 1  # Each thread is rendered as one line
        target_y = self.selected_index * line_height

        # Get viewport height (visible area)
        viewport_height = self.size.height

        # If selected item is above viewport, scroll up
        if target_y < self.scroll_y:
            self.scroll_to(y=target_y, animate=False)
        # If selected item is below viewport, scroll down
        elif target_y >= self.scroll_y + viewport_height:
            self.scroll_to(y=target_y - viewport_height + 1, animate=False)

    def get_selected_thread(self) -> Optional[CommentThread]:
        """Get the currently selected thread."""
        if 0 <= self.selected_index < len(self.threads):
            return self.threads[self.selected_index]
        return None

    class FocusInput(Message):
        """Message sent when user presses Enter to focus input."""
        pass

    class CloseThread(Message):
        """Message sent when user presses Ctrl+T to close selected thread."""
        def __init__(self, thread: CommentThread) -> None:
            self.thread = thread
            super().__init__()

    class ReopenThread(Message):
        """Message sent when user presses Ctrl+T to reopen a closed thread."""
        def __init__(self, thread: CommentThread) -> None:
            self.thread = thread
            super().__init__()

    def on_key(self, event) -> None:
        """Handle key events for navigation."""
        if event.key == "down" or event.key == "j":
            self.move_selection(1)
            event.prevent_default()
        elif event.key == "up" or event.key == "k":
            self.move_selection(-1)
            event.prevent_default()
        elif event.key == "pagedown" or event.key == "ctrl+d":
            self.move_selection(5)
            event.prevent_default()
        elif event.key == "pageup" or event.key == "ctrl+u":
            self.move_selection(-5)
            event.prevent_default()
        elif event.key == "home" or event.key == "g":
            self.selected_index = 0
            self.refresh()
            self._scroll_to_selected()
            if self.threads:
                self.post_message(
                    self.ThreadSelected(
                        thread=self.threads[0],
                        index=0
                    )
                )
            event.prevent_default()
        elif event.key == "end" or event.key == "G":
            if self.threads:
                self.selected_index = len(self.threads) - 1
                self.refresh()
                self._scroll_to_selected()
                self.post_message(
                    self.ThreadSelected(
                        thread=self.threads[self.selected_index],
                        index=self.selected_index
                    )
                )
            event.prevent_default()
        elif event.key == "enter":
            # User wants to focus the input to type a message
            self.post_message(self.FocusInput())
            event.prevent_default()
        elif event.key == "ctrl+t":
            # Toggle: Close active threads, reopen closed threads
            if 0 <= self.selected_index < len(self.threads):
                thread = self.threads[self.selected_index]
                if thread.status == ThreadStatus.ACTIVE:
                    self.post_message(self.CloseThread(thread))
                elif thread.status == ThreadStatus.COMPLETED:
                    self.post_message(self.ReopenThread(thread))
            event.prevent_default()
        elif event.key == "right":
            # Cycle to next view
            self.cycle_view(1)
            event.prevent_default()
        elif event.key == "left":
            # Cycle to previous view
            self.cycle_view(-1)
            event.prevent_default()
