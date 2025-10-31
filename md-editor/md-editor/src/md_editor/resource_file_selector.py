"""Resource file selector widget with checkbox selection."""

from pathlib import Path
from typing import List, Set
from textual.scroll_view import ScrollView
from textual.message import Message
from textual.reactive import reactive
from textual.geometry import Size
from textual.strip import Strip
from rich.text import Text
from rich.style import Style


class ResourceFileSelector(ScrollView):
    """Widget for selecting resource files with checkboxes."""

    selected_index = reactive(0)
    can_focus = True

    class SelectionConfirmed(Message):
        """Message sent when user confirms selection."""

        def __init__(self, selected_files: List[str]) -> None:
            self.selected_files = selected_files
            super().__init__()

    class SelectionCancelled(Message):
        """Message sent when user cancels selection."""
        pass

    def __init__(
        self,
        available_files: List[Path],
        initially_selected: List[str],
        *args,
        **kwargs
    ):
        """Initialize the resource file selector.

        Args:
            available_files: List of Path objects for available markdown files
            initially_selected: List of absolute path strings that should start checked
        """
        super().__init__(*args, **kwargs)
        self.available_files = available_files
        self.selected_index = 0 if available_files else -1

        # Convert initially_selected to absolute paths and store as set
        self.checked_files: Set[str] = {
            str(Path(f).absolute()) for f in initially_selected
        }

        # Disable horizontal scrolling
        self.show_horizontal_scrollbar = False

    @property
    def virtual_size(self) -> Size:
        """Return the virtual size for scrolling."""
        width = self.size.width
        height = len(self.available_files) if self.available_files else 1
        return Size(width, height)

    def render_line(self, y: int) -> Strip:
        """Render a single line of the file list with checkbox."""
        scroll_x, scroll_y = self.scroll_offset
        line_index = scroll_y + y

        # If no files, show empty message
        if not self.available_files:
            if y == 0:
                text = Text("No markdown files found in directory", style=Style(dim=True, italic=True))
                return Strip(text.render(self.app.console))
            else:
                return Strip.blank(self.size.width)

        # If beyond content, return blank
        if line_index >= len(self.available_files):
            return Strip.blank(self.size.width)

        # Get the file for this line
        file_path = self.available_files[line_index]
        file_name = file_path.name
        is_checked = str(file_path.absolute()) in self.checked_files

        # Checkbox character
        checkbox = "[✓] " if is_checked else "[ ] "

        # Build line with selection indicator
        cursor = "> " if line_index == self.selected_index else "  "

        # Calculate available width and truncate filename if needed
        max_width = self.size.width - len(cursor) - len(checkbox) - 1

        if len(file_name) > max_width:
            file_name = file_name[:max_width-3] + "..."

        line_text = f"{cursor}{checkbox}{file_name}"

        # Highlight selected line
        if line_index == self.selected_index:
            text = Text(line_text, style=Style(bgcolor="blue", color="white", bold=True))
        else:
            text = Text(line_text)

        return Strip(text.render(self.app.console))

    def toggle_current(self) -> None:
        """Toggle checkbox for currently selected file."""
        if not self.available_files or self.selected_index < 0:
            return

        if 0 <= self.selected_index < len(self.available_files):
            file_path = str(self.available_files[self.selected_index].absolute())

            if file_path in self.checked_files:
                self.checked_files.remove(file_path)
            else:
                self.checked_files.add(file_path)

            self.refresh()

    def move_selection(self, delta: int) -> None:
        """Move selection by delta positions."""
        if not self.available_files:
            return

        new_index = self.selected_index + delta
        self.selected_index = max(0, min(new_index, len(self.available_files) - 1))
        self.refresh()

        # Scroll to keep selected item visible
        self._scroll_to_selected()

    def _scroll_to_selected(self) -> None:
        """Scroll to make the selected file visible."""
        if not self.available_files or self.selected_index < 0:
            return

        line_height = 1
        target_y = self.selected_index * line_height
        viewport_height = self.size.height

        # If selected item is above viewport, scroll up
        if target_y < self.scroll_y:
            self.scroll_to(y=target_y, animate=False)
        # If selected item is below viewport, scroll down
        elif target_y >= self.scroll_y + viewport_height:
            self.scroll_to(y=target_y - viewport_height + 1, animate=False)

    def confirm_selection(self) -> None:
        """Confirm selection and post message with selected files."""
        selected_files = sorted(list(self.checked_files))
        self.post_message(self.SelectionConfirmed(selected_files))

    def cancel_selection(self) -> None:
        """Cancel selection without changes."""
        self.post_message(self.SelectionCancelled())

    def on_key(self, event) -> None:
        """Handle key events for navigation and selection."""
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
            event.prevent_default()
        elif event.key == "end" or event.key == "G":
            if self.available_files:
                self.selected_index = len(self.available_files) - 1
                self.refresh()
                self._scroll_to_selected()
            event.prevent_default()
        elif event.key == "space":
            # Toggle checkbox
            self.toggle_current()
            event.prevent_default()
        elif event.key == "enter":
            # Confirm selection
            self.confirm_selection()
            event.prevent_default()
        elif event.key == "escape":
            # Cancel
            self.cancel_selection()
            event.prevent_default()
