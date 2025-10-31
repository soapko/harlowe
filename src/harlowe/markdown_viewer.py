"""Markdown viewer widget with vim-style navigation and visual selection."""

from typing import Optional, Tuple
from textual.widget import Widget
from textual.scroll_view import ScrollView
from textual.reactive import reactive
from textual.message import Message
from textual.geometry import Region, Spacing, Size
from textual.strip import Strip
from rich.text import Text
from rich.segment import Segment
from rich.style import Style
from rich.console import Console
from rich.markdown import Markdown
from io import StringIO
import textwrap
import markdown_it


class MarkdownViewer(ScrollView):
    """A scrollable markdown viewer with line numbers and visual selection."""

    cursor_line = reactive(0)
    visual_mode = reactive(False)
    visual_start = reactive(0)
    visual_end = reactive(0)
    commenting_mode = reactive(False)  # Keep selection visible while commenting
    comment_start = reactive(0)
    comment_end = reactive(0)

    class SelectionMade(Message):
        """Message sent when a selection is made."""

        def __init__(self, selected_text: str, line_start: int, line_end: int) -> None:
            self.selected_text = selected_text
            self.line_start = line_start
            self.line_end = line_end
            super().__init__()

    class ViewerScrolled(Message):
        """Message sent when the viewer is scrolled."""

        def __init__(self, line_number: int) -> None:
            self.line_number = line_number
            super().__init__()

    def __init__(self, file_path: str | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = file_path
        self.lines: list[str] = []
        self.total_lines = 0
        self.can_focus = True
        self.soft_wrap = True  # Enable soft wrapping by default
        self.wrapped_lines: list[tuple[int, str]] = []  # List of (original_line_idx, wrapped_text)
        self._programmatic_scroll = False  # Track if scroll is from keyboard navigation
        self._suppress_scroll_events = False  # Suppress scroll events during sync

        # Rich markdown rendering infrastructure
        self.use_rich_rendering = True  # Toggle for Rich markdown rendering
        self.rendered_lines: list[list[Segment]] = []  # Cached Rich-rendered lines
        self.display_to_source: dict[int, int] = {}  # Map display line -> source line

        if file_path:
            self._load_file()
        else:
            # No file loaded yet - show placeholder
            self.lines = ["No file loaded. Press Ctrl+O to open a file."]
            self.total_lines = 1
        # Set virtual size after loading
        self._update_virtual_size()

    def _load_file(self) -> None:
        """Load the markdown file."""
        if not self.file_path:
            self.lines = ["No file loaded."]
            self.total_lines = 1
            return

        try:
            with open(self.file_path, 'r') as f:
                content = f.read()
                self.lines = content.splitlines()
                self.total_lines = len(self.lines)
        except Exception as e:
            self.lines = [f"Error loading file: {str(e)}"]
            self.total_lines = 1

    def watch_cursor_line(self, old_value: int, new_value: int) -> None:
        """
        Watch cursor_line changes and ensure it always points to a rendered line.

        This prevents the cursor from ever landing on un-rendered lines (like code block
        interiors) by automatically correcting the position to the nearest valid line.
        """
        # Skip validation if we're in the middle of initialization
        if not hasattr(self, 'lines') or not self.lines:
            return

        # Skip if wrapped_lines not ready (still initializing)
        if not hasattr(self, 'wrapped_lines') or not self.wrapped_lines:
            return

        # Skip if display_to_source not ready (during Rich rendering initialization)
        if self.use_rich_rendering and not self.display_to_source:
            return

        # Check if current cursor line has content
        if not self._source_line_has_content(new_value):
            # Cursor landed on a non-rendered line - find nearest valid line
            # Prefer forward to avoid jumping backwards unexpectedly
            corrected_line = self._find_nearest_content_line(new_value, prefer_forward=True)

            # Only update if different (prevent infinite loop)
            if corrected_line != new_value:
                self.cursor_line = corrected_line

    def _render_markdown_with_rich(self, width: int) -> None:
        """
        Render markdown using Rich and build display-to-source line mapping.

        Uses block-based strategy: Parse markdown into blocks using markdown-it,
        render with Rich, then sequentially assign display line ranges to blocks.
        This provides deterministic, robust mapping for cursor positioning and selection.
        """
        if not self.use_rich_rendering:
            return

        # Prepare content
        markdown_text = '\n'.join(self.lines)

        # Parse markdown into blocks using markdown-it
        md = markdown_it.MarkdownIt()
        tokens = md.parse(markdown_text)

        # Extract blocks with source line ranges from tokens
        # Strategy: Track individual content blocks, skip containers to avoid duplicates
        blocks = []
        in_list_item = False  # Track if we're inside a list item
        list_item_stack = []  # Stack to track nested list items

        for i, token in enumerate(tokens):
            if hasattr(token, 'map') and token.map:
                # Track list item context to avoid capturing redundant paragraphs
                if token.type == 'list_item_open':
                    list_item_stack.append(token.map)
                elif token.type == 'list_item_close':
                    if list_item_stack:
                        list_item_stack.pop()

                in_list_item = len(list_item_stack) > 0

                # Capture specific block types:
                # - headings (always)
                # - list_item_open (for list items)
                # - paragraph_open (only if NOT inside a list item, to avoid duplication)
                # - fence (code blocks)
                # - hr (horizontal rules)
                # - table_open (tables)
                # Skip containers: ordered_list_open, bullet_list_open, blockquote_open

                should_capture = False
                if token.type in ['heading_open', 'fence', 'hr', 'table_open', 'list_item_open']:
                    should_capture = True
                elif token.type == 'paragraph_open' and not in_list_item:
                    should_capture = True

                if should_capture:
                    source_start, source_end = token.map
                    blocks.append({
                        'type': token.type,
                        'source_start': source_start,  # 0-indexed, inclusive
                        'source_end': source_end - 1,   # Make inclusive
                        'display_start': None,          # Will be assigned
                        'display_end': None             # Will be assigned
                    })

        # Render full document with Rich
        console = Console(width=width, file=StringIO(), legacy_windows=False)
        markdown_obj = Markdown(markdown_text)
        self.rendered_lines = list(console.render_lines(markdown_obj, console.options))

        # Build display-to-source mapping
        # Simple strategy: Map each display line to its proportional source line
        self.display_to_source = {}

        total_display = len(self.rendered_lines)
        total_source = len(self.lines)

        if total_source == 0:
            for i in range(total_display):
                self.display_to_source[i] = 0
        else:
            # Map proportionally: display_line N maps to source line N * (total_source / total_display)
            for display_idx in range(total_display):
                # Calculate proportional source line
                source_idx = int((display_idx / max(1, total_display)) * total_source)
                # Clamp to valid range
                source_idx = max(0, min(source_idx, total_source - 1))
                self.display_to_source[display_idx] = source_idx

        # Build wrapped_lines format for compatibility with existing code
        # Format: (original_line_idx, wrapped_text)
        self.wrapped_lines = []
        for display_idx, segments in enumerate(self.rendered_lines):
            source_idx = self.display_to_source.get(display_idx, 0)
            text = "".join(seg.text for seg in segments)
            self.wrapped_lines.append((source_idx, text))

    def _wrap_lines(self, width: int) -> None:
        """Wrap lines to fit within the given width."""
        line_num_width = 5  # Width for line numbers
        content_width = max(40, width - line_num_width)  # Minimum 40 chars for content

        if self.use_rich_rendering:
            # Use Rich markdown rendering
            self._render_markdown_with_rich(content_width)
        else:
            # Fall back to plain text wrapping
            self.wrapped_lines = []
            for idx, line in enumerate(self.lines):
                if not self.soft_wrap or len(line) <= content_width:
                    # No wrapping needed
                    self.wrapped_lines.append((idx, line))
                else:
                    # Wrap the line
                    wrapped = textwrap.wrap(line, width=content_width,
                                           break_long_words=False,
                                           break_on_hyphens=False)
                    if not wrapped:  # Empty line or just whitespace
                        self.wrapped_lines.append((idx, line))
                    else:
                        for wrapped_line in wrapped:
                            self.wrapped_lines.append((idx, wrapped_line))

    def reload_file(self) -> int:
        """Reload the file and return the new cursor position."""
        old_cursor = self.cursor_line
        self._load_file()

        # Regenerate wrapped lines and update virtual size for new content
        self._update_virtual_size()

        # Smart position preservation: try to keep same line, or adjust proportionally
        if old_cursor >= self.total_lines:
            new_cursor = max(0, self.total_lines - 1)
        else:
            new_cursor = old_cursor

        # Find nearest line with content (prevents cursor landing on blank lines after reload)
        new_cursor = self._find_nearest_content_line(new_cursor, prefer_forward=True)

        self.cursor_line = new_cursor
        self.visual_mode = False
        self.refresh()
        return new_cursor

    def render_line(self, y: int) -> Strip:
        """Render a single line of the markdown content."""
        # Ensure wrapped lines are up to date
        if not self.wrapped_lines or len(self.wrapped_lines) == 0:
            self._wrap_lines(self.size.width)

        scroll_x, scroll_y = self.scroll_offset
        wrapped_index = scroll_y + y  # Index into wrapped_lines

        # If beyond the content, return empty strip
        if wrapped_index >= len(self.wrapped_lines):
            return Strip.blank(self.size.width)

        # Get the original line index
        original_line_idx, line_text = self.wrapped_lines[wrapped_index]

        # Line number (show the original line number)
        line_num_str = f"{original_line_idx + 1:4d} "

        # Check if this line is selected or being commented on
        is_selected = False
        is_commenting = False
        is_cursor = (original_line_idx == self.cursor_line)

        if self.visual_mode:
            start = min(self.visual_start, self.visual_end)
            end = max(self.visual_start, self.visual_end)
            is_selected = start <= original_line_idx <= end

        if self.commenting_mode:
            start = min(self.comment_start, self.comment_end)
            end = max(self.comment_start, self.comment_end)
            is_commenting = start <= original_line_idx <= end

        # Build the segments for this line
        segments = []

        # Style the line number
        if is_commenting or is_selected:
            segments.append(Segment(line_num_str, Style(color="yellow", bold=True)))
        elif is_cursor:
            segments.append(Segment(line_num_str, Style(color="cyan", bold=True)))
        else:
            segments.append(Segment(line_num_str, Style(dim=True)))

        # Get line content segments
        if self.use_rich_rendering and wrapped_index < len(self.rendered_lines):
            # Use Rich-rendered segments
            content_segments = list(self.rendered_lines[wrapped_index])
        else:
            # Fall back to plain text
            content_segments = [Segment(line_text)]

        # Apply selection/cursor styling if needed
        if is_commenting or is_selected:
            # Override Rich styling with selection highlighting
            content_segments = [Segment(seg.text, Style(color="black", bgcolor="yellow"))
                              for seg in content_segments]
        elif is_cursor and not self.visual_mode and not self.commenting_mode:
            # Override Rich styling with cursor highlighting
            content_segments = [Segment(seg.text, Style(color="white", bgcolor="blue"))
                              for seg in content_segments]

        # Combine line number and content
        segments.extend(content_segments)

        # Apply the widget's rich_style (from CSS) to the strip
        strip = Strip(segments)
        return strip.apply_style(self.rich_style)

    def _update_virtual_size(self) -> None:
        """Update the virtual size to enable scrolling for all lines."""
        # Wrap lines based on current width
        if self.size.width > 0:
            self._wrap_lines(self.size.width)

        # Calculate the width needed (line number + space + content)
        # For wrapped view, use current width
        max_line_width = self.size.width if self.size.width > 0 else 80

        # Set virtual size: each wrapped line is 1 row tall
        num_rows = len(self.wrapped_lines) if self.wrapped_lines else self.total_lines
        self.virtual_size = Size(max_line_width, num_rows)

    def on_resize(self, event) -> None:
        """Handle resize events to rewrap text."""
        self._update_virtual_size()
        self.refresh()

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        """Watch for scroll changes and update cursor position to follow mouse scrolling."""
        # Call parent implementation first
        super().watch_scroll_y(old_value, new_value)

        # Don't update cursor if in commenting mode (would disrupt selection)
        if self.commenting_mode:
            return

        # Don't update cursor if this is programmatic scroll (from keyboard navigation)
        if self._programmatic_scroll:
            return

        # Only update if scroll changed significantly
        if abs(round(old_value) - round(new_value)) > 0:
            self._update_cursor_from_scroll()

            # Emit scroll event for synchronization (unless suppressed)
            if not self._suppress_scroll_events:
                scroll_x, scroll_y = self.scroll_offset
                # Calculate the source line at the top of the viewport
                if 0 <= scroll_y < len(self.wrapped_lines):
                    source_line, _ = self.wrapped_lines[int(scroll_y)]
                    self.post_message(self.ViewerScrolled(line_number=source_line + 1))

    def _update_cursor_from_scroll(self) -> None:
        """Update cursor_line to match current scroll position."""
        scroll_x, scroll_y = self.scroll_offset
        viewport_height = self.size.height

        # Calculate target line: top 20% of viewport
        target_display_line = int(scroll_y + viewport_height * 0.2)

        # Ensure wrapped_lines is up to date
        if not self.wrapped_lines:
            self._wrap_lines(self.size.width)

        # Convert display line to original line number
        if 0 <= target_display_line < len(self.wrapped_lines):
            original_line_idx, _ = self.wrapped_lines[target_display_line]

            # Clamp to valid range
            original_line_idx = max(0, min(original_line_idx, self.total_lines - 1))

            # Find nearest line with content (CRITICAL FIX: prevents cursor vanishing)
            original_line_idx = self._find_nearest_content_line(original_line_idx, prefer_forward=True)

            # Only update if cursor moved to different line
            if original_line_idx != self.cursor_line:
                self.cursor_line = original_line_idx

                # If in visual mode, update visual_end
                if self.visual_mode:
                    self.visual_end = self.cursor_line

                # Refresh to show new cursor position
                self.refresh()

    def _source_line_has_content(self, source_line: int) -> bool:
        """
        Check if a source line has meaningful content that is actually rendered.

        This checks both:
        1. Whether the source line has text content
        2. Whether the source line has corresponding display lines (Rich rendering)

        This helps skip empty lines AND un-rendered lines (like code block internals)
        during cursor navigation.

        Args:
            source_line: The source line number (0-indexed)

        Returns:
            True if the source line has rendered content, False otherwise
        """
        # Check bounds
        if not (0 <= source_line < len(self.lines)):
            return False

        # Check if source line has text content
        source_text = self.lines[source_line].strip()
        if not source_text:
            return False

        # When using Rich rendering, also check if this source line has display lines
        if self.use_rich_rendering and self.display_to_source:
            # Check if any display line maps to this source line
            has_display_line = any(
                src_line == source_line
                for src_line in self.display_to_source.values()
            )
            return has_display_line

        # For non-Rich rendering, just check text content
        return True

    def _find_nearest_content_line(self, target_line: int, prefer_forward: bool = True) -> int:
        """
        Find the nearest line with content starting from target_line.

        Args:
            target_line: Starting line number (0-indexed)
            prefer_forward: If True, search forward first, then backward. Otherwise reverse.

        Returns:
            The nearest line number with content (0-indexed), or target_line if none found
        """
        target_line = max(0, min(target_line, self.total_lines - 1))

        # If target line already has content, return it
        if self._source_line_has_content(target_line):
            return target_line

        # Search for nearest content line
        max_search_distance = self.total_lines  # Search entire document if needed

        for offset in range(1, max_search_distance):
            if prefer_forward:
                # Try forward first
                if target_line + offset < self.total_lines:
                    if self._source_line_has_content(target_line + offset):
                        return target_line + offset
                # Then try backward
                if target_line - offset >= 0:
                    if self._source_line_has_content(target_line - offset):
                        return target_line - offset
            else:
                # Try backward first
                if target_line - offset >= 0:
                    if self._source_line_has_content(target_line - offset):
                        return target_line - offset
                # Then try forward
                if target_line + offset < self.total_lines:
                    if self._source_line_has_content(target_line + offset):
                        return target_line + offset

        # If no content line found (shouldn't happen), return original target
        return target_line

    def _get_cursor_display_position(self) -> int:
        """
        Find the first wrapped line index that corresponds to cursor_line.

        Returns:
            The index in wrapped_lines where the cursor's original line appears.
        """
        if not self.wrapped_lines:
            return 0

        for idx, (orig_line_idx, _) in enumerate(self.wrapped_lines):
            if orig_line_idx == self.cursor_line:
                return idx

        # Fallback: return position proportional to file
        if self.total_lines > 0:
            ratio = self.cursor_line / self.total_lines
            return int(ratio * len(self.wrapped_lines))

        return 0

    def move_cursor(self, delta: int) -> None:
        """
        Move the cursor by delta lines, skipping empty/decorative-only lines.

        Args:
            delta: Number of lines to move (positive = down, negative = up)
        """
        direction = 1 if delta > 0 else -1
        new_pos = self.cursor_line + direction

        # Skip empty/decorative lines to find next line with content
        max_attempts = abs(delta) * 2 + 20  # Prevent infinite loop
        attempts = 0

        while 0 <= new_pos < self.total_lines and attempts < max_attempts:
            if self._source_line_has_content(new_pos):
                # Found a line with visible content
                break
            new_pos += direction
            attempts += 1

        # Clamp to valid range
        self.cursor_line = max(0, min(new_pos, self.total_lines - 1))

        if self.visual_mode:
            self.visual_end = self.cursor_line

        # Auto-scroll with 10% top/bottom bands
        viewport_height = self.size.height
        scroll_x, scroll_y = self.scroll_offset

        # Calculate cursor position in display coordinates
        cursor_display_pos = self._get_cursor_display_position()
        cursor_viewport_pos = cursor_display_pos - scroll_y

        # Calculate 10% boundaries
        top_band = int(viewport_height * 0.1)
        bottom_band = viewport_height - int(viewport_height * 0.1)

        # Only scroll if cursor enters the top or bottom 10% bands
        self._programmatic_scroll = True  # Mark as keyboard navigation scroll
        try:
            if cursor_viewport_pos < top_band:
                # Cursor in top band, scroll up
                target_y = max(0, cursor_display_pos - top_band)
                self.scroll_to(y=target_y, animate=False)
            elif cursor_viewport_pos >= bottom_band:
                # Cursor in bottom band, scroll down
                target_y = max(0, cursor_display_pos - bottom_band + 1)
                self.scroll_to(y=target_y, animate=False)
        finally:
            self._programmatic_scroll = False  # Reset flag

        self.refresh()

    def move_to_line(self, line: int) -> None:
        """
        Move cursor to specific line (0-indexed).

        If the target line is empty/decorative, finds the nearest line with content.

        Args:
            line: Target line number (0-indexed)
        """
        target_line = max(0, min(line, self.total_lines - 1))

        # Find nearest line with content
        target_line = self._find_nearest_content_line(target_line, prefer_forward=True)

        self.cursor_line = target_line

        if self.visual_mode:
            self.visual_end = self.cursor_line

        # Auto-scroll with 10% top/bottom bands
        viewport_height = self.size.height
        scroll_x, scroll_y = self.scroll_offset

        # Calculate cursor position in display coordinates
        cursor_display_pos = self._get_cursor_display_position()
        cursor_viewport_pos = cursor_display_pos - scroll_y

        # Calculate 10% boundaries
        top_band = int(viewport_height * 0.1)
        bottom_band = viewport_height - int(viewport_height * 0.1)

        # Only scroll if cursor enters the top or bottom 10% bands
        self._programmatic_scroll = True  # Mark as keyboard navigation scroll
        try:
            if cursor_viewport_pos < top_band:
                # Cursor in top band, scroll up
                target_y = max(0, cursor_display_pos - top_band)
                self.scroll_to(y=target_y, animate=False)
            elif cursor_viewport_pos >= bottom_band:
                # Cursor in bottom band, scroll down
                target_y = max(0, cursor_display_pos - bottom_band + 1)
                self.scroll_to(y=target_y, animate=False)
        finally:
            self._programmatic_scroll = False  # Reset flag

        self.refresh()

    def toggle_visual_mode(self) -> None:
        """Toggle visual selection mode."""
        if not self.visual_mode:
            # Enter visual mode
            self.visual_mode = True
            self.visual_start = self.cursor_line
            self.visual_end = self.cursor_line
        else:
            # Exit visual mode WITHOUT capturing (just cancel)
            self.visual_mode = False

        self.refresh()

    def cancel_visual_mode(self) -> None:
        """Cancel visual mode without capturing selection."""
        self.visual_mode = False
        self.refresh()

    def capture_selection(self) -> None:
        """Capture the current visual selection (called on Enter)."""
        if not self.visual_mode:
            return
        self._capture_selection()

    def _capture_selection(self) -> None:
        """Capture the current visual selection and send message."""
        if not self.visual_mode:
            return

        start = min(self.visual_start, self.visual_end)
        end = max(self.visual_start, self.visual_end)

        selected_lines = self.lines[start:end + 1]
        selected_text = "\n".join(selected_lines)

        # Exit visual mode and enter commenting mode
        self.visual_mode = False
        self.commenting_mode = True
        self.comment_start = start
        self.comment_end = end

        # Send message
        self.post_message(
            self.SelectionMade(
                selected_text=selected_text,
                line_start=start + 1,  # 1-indexed for display
                line_end=end + 1
            )
        )

    def clear_commenting_mode(self) -> None:
        """Clear commenting mode (after comment submitted or cancelled)."""
        self.commenting_mode = False
        self.refresh()

    def get_cursor_position(self) -> int:
        """Get the current cursor position."""
        return self.cursor_line

    def page_down(self) -> None:
        """Move down one page."""
        # Approximate page size
        page_size = 20
        self.move_cursor(page_size)

    def page_up(self) -> None:
        """Move up one page."""
        page_size = 20
        self.move_cursor(-page_size)

    def _get_display_line_for_source(self, source_line: int) -> int:
        """
        Find the first display line that corresponds to a given source line.

        Args:
            source_line: The source line number (0-indexed)

        Returns:
            The display line index (0-indexed) where this source line appears
        """
        if not self.wrapped_lines:
            return 0

        # Search for first display line that maps to this source line
        for idx, (orig_line_idx, _) in enumerate(self.wrapped_lines):
            if orig_line_idx == source_line:
                return idx

        # Fallback: return proportional position if exact match not found
        if self.total_lines > 0:
            ratio = source_line / self.total_lines
            return int(ratio * len(self.wrapped_lines))

        return 0

    def scroll_to_line(self, line_number: int, suppress_events: bool = False) -> None:
        """
        Scroll to a specific source line number (1-indexed).

        Args:
            line_number: The source line number to scroll to (1-indexed)
            suppress_events: If True, don't emit ViewerScrolled events (for sync)
        """
        # Convert to 0-indexed source line
        target_line = line_number - 1
        target_line = max(0, min(target_line, self.total_lines - 1))

        # Convert source line to display line (critical for Rich rendering)
        target_display_line = self._get_display_line_for_source(target_line)

        # Scroll to position the target line in the middle of viewport
        viewport_height = self.size.height
        target_scroll_y = max(0, target_display_line - viewport_height // 2)

        # Suppress events if requested (for sync)
        old_suppress = self._suppress_scroll_events
        self._suppress_scroll_events = suppress_events
        try:
            self.scroll_to(y=target_scroll_y, animate=False)
            self.refresh()
        finally:
            self._suppress_scroll_events = old_suppress
