"""File picker widget for browsing and selecting markdown files."""

from pathlib import Path
from typing import List, Optional
from textual.scroll_view import ScrollView
from textual.message import Message
from textual.reactive import reactive
from textual.geometry import Size
from textual.strip import Strip
from rich.text import Text
from rich.style import Style


class FileBrowser(ScrollView):
    """Widget for browsing directories and selecting a markdown file."""

    selected_index = reactive(0)
    can_focus = True

    class FileSelected(Message):
        """Message sent when user selects a file."""

        def __init__(self, file_path: str) -> None:
            self.file_path = file_path
            super().__init__()

    class SelectionCancelled(Message):
        """Message sent when user cancels selection."""
        pass

    def __init__(
        self,
        start_path: Path,
        *args,
        **kwargs
    ):
        """Initialize the file browser.

        Args:
            start_path: Starting directory path
        """
        super().__init__(*args, **kwargs)
        self.current_path = start_path.resolve()
        self.items: List[tuple[str, Path, bool]] = []  # (display_name, path, is_dir)
        self.selected_index = 0

        # Disable horizontal scrolling
        self.show_horizontal_scrollbar = False

        # Load initial directory
        self._load_directory()

    def _load_directory(self) -> None:
        """Load contents of current directory."""
        self.items = []

        try:
            # Add parent directory entry if not at root
            if self.current_path.parent != self.current_path:
                self.items.append(("..", self.current_path.parent, True))

            # Get all entries
            entries = list(self.current_path.iterdir())

            # Separate directories and md files
            directories = []
            md_files = []

            for entry in entries:
                if entry.is_dir():
                    # Skip hidden directories (starting with .)
                    if not entry.name.startswith('.'):
                        directories.append((entry.name + "/", entry, True))
                elif entry.is_file() and entry.suffix == '.md':
                    md_files.append((entry.name, entry, False))

            # Sort and combine: directories first, then files
            directories.sort(key=lambda x: x[0].lower())
            md_files.sort(key=lambda x: x[0].lower())

            self.items.extend(directories)
            self.items.extend(md_files)

        except PermissionError:
            # Can't read directory, add error message
            self.items = [("(Permission denied)", self.current_path, False)]
        except Exception as e:
            # Other error
            self.items = [(f"(Error: {str(e)})", self.current_path, False)]

        # Reset selection to first item
        self.selected_index = 0
        self.refresh()

    @property
    def virtual_size(self) -> Size:
        """Return the virtual size for scrolling."""
        width = self.size.width
        # Add 1 for path display line at top
        height = len(self.items) + 1 if self.items else 2
        return Size(width, height)

    def render_line(self, y: int) -> Strip:
        """Render a single line of the file browser."""
        scroll_x, scroll_y = self.scroll_offset
        line_index = scroll_y + y

        # First line: current path
        if line_index == 0:
            path_text = f"📁 {self.current_path}"
            text = Text(path_text, style=Style(bold=True, color="cyan"))
            return Strip(text.render(self.app.console))

        # Adjust for path line
        item_index = line_index - 1

        # If no items, show empty message
        if not self.items:
            if item_index == 0:
                text = Text("No markdown files found", style=Style(dim=True, italic=True))
                return Strip(text.render(self.app.console))
            else:
                return Strip.blank(self.size.width)

        # If beyond content, return blank
        if item_index >= len(self.items):
            return Strip.blank(self.size.width)

        # Get the item for this line
        display_name, item_path, is_dir = self.items[item_index]

        # Build line with selection indicator
        cursor = "> " if item_index == self.selected_index else "  "

        # Add icon for directories
        if is_dir:
            icon = "📂 " if display_name != ".." else "⬆️  "
        else:
            icon = "📄 "

        # Calculate available width and truncate if needed
        prefix_len = len(cursor) + len(icon)
        max_width = self.size.width - prefix_len - 1

        if len(display_name) > max_width:
            display_name = display_name[:max_width-3] + "..."

        line_text = f"{cursor}{icon}{display_name}"

        # Highlight selected line
        if item_index == self.selected_index:
            text = Text(line_text, style=Style(bgcolor="blue", color="white", bold=True))
        else:
            # Dim directories slightly
            style = Style(dim=True) if is_dir else Style()
            text = Text(line_text, style=style)

        return Strip(text.render(self.app.console))

    def move_selection(self, delta: int) -> None:
        """Move selection by delta positions."""
        if not self.items:
            return

        new_index = self.selected_index + delta
        self.selected_index = max(0, min(new_index, len(self.items) - 1))
        self.refresh()

        # Scroll to keep selected item visible
        self._scroll_to_selected()

    def _scroll_to_selected(self) -> None:
        """Scroll to make the selected item visible."""
        if not self.items or self.selected_index < 0:
            return

        # Add 1 because first line is path display
        target_y = self.selected_index + 1
        viewport_height = self.size.height

        # If selected item is above viewport, scroll up
        if target_y < self.scroll_y:
            self.scroll_to(y=target_y, animate=False)
        # If selected item is below viewport, scroll down
        elif target_y >= self.scroll_y + viewport_height:
            self.scroll_to(y=target_y - viewport_height + 1, animate=False)

    def select_current(self) -> None:
        """Select current item (navigate if directory, select if file)."""
        if not self.items or self.selected_index < 0:
            return

        if 0 <= self.selected_index < len(self.items):
            display_name, item_path, is_dir = self.items[self.selected_index]

            if is_dir:
                # Navigate into directory
                self.current_path = item_path.resolve()
                self._load_directory()
            else:
                # Select file (only if it's a real file, not error message)
                if item_path.exists() and item_path.is_file():
                    self.post_message(self.FileSelected(str(item_path)))

    def cancel_selection(self) -> None:
        """Cancel selection without choosing a file."""
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
            self.move_selection(10)
            event.prevent_default()
        elif event.key == "pageup" or event.key == "ctrl+u":
            self.move_selection(-10)
            event.prevent_default()
        elif event.key == "home" or event.key == "g":
            self.selected_index = 0
            self.refresh()
            self._scroll_to_selected()
            event.prevent_default()
        elif event.key == "end" or event.key == "G":
            if self.items:
                self.selected_index = len(self.items) - 1
                self.refresh()
                self._scroll_to_selected()
            event.prevent_default()
        elif event.key == "enter":
            # Select or navigate
            self.select_current()
            event.prevent_default()
        elif event.key == "escape":
            # Cancel
            self.cancel_selection()
            event.prevent_default()
