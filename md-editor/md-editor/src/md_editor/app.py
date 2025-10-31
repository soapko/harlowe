"""Main Textual application for markdown editing."""

import os
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Label
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen

from .markdown_viewer import MarkdownViewer
from .comment_input import CommentInput
from .edit_panel import EditPanel
from .thread_manager_concurrent import ClaudeThreadManager
from .config import Config
from .thread_chat_panel import ThreadChatPanel
from .thread_persistence import ThreadPersistence
from .thread_selector import ThreadSelector
from .models import CommentThread, ThreadStatus, ThreadViewMode
from .resource_file_selector import ResourceFileSelector
from .resource_file_manager import ResourceFileManager
from .file_picker import FileBrowser
from .undo_manager import UndoManager
from .git_manager import GitManager
from .merge_coordinator import MergeCoordinator


class ResourceFileScreen(Screen):
    """Modal screen for selecting resource files."""

    CSS = """
    ResourceFileScreen {
        align: center middle;
    }

    #resource-dialog {
        width: 80;
        height: 24;
        border: thick $background 80%;
        background: $surface;
    }

    #dialog-title {
        background: $boost;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }

    #dialog-instructions {
        padding: 0 1;
        color: $text-muted;
        text-style: italic;
    }

    ResourceFileSelector {
        height: 1fr;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=False),
    ]

    def __init__(self, available_files, initially_selected, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.available_files = available_files
        self.initially_selected = initially_selected

    def compose(self) -> ComposeResult:
        """Create the dialog layout."""
        with Vertical(id="resource-dialog"):
            yield Label("📎 Select Resource Files", id="dialog-title")
            yield Label("Space=toggle • Enter=confirm • Esc=cancel", id="dialog-instructions")
            yield ResourceFileSelector(
                available_files=self.available_files,
                initially_selected=self.initially_selected
            )

    def on_key(self, event) -> None:
        """Prevent all key events from bubbling to app."""
        event.stop()

    def on_resource_file_selector_selection_confirmed(
        self, message: ResourceFileSelector.SelectionConfirmed
    ) -> None:
        """Handle selection confirmation."""
        message.stop()
        self.dismiss(message.selected_files)

    def on_resource_file_selector_selection_cancelled(
        self, message: ResourceFileSelector.SelectionCancelled
    ) -> None:
        """Handle selection cancellation."""
        message.stop()
        self.dismiss(None)


class FilePickerScreen(Screen):
    """Modal screen for browsing and selecting markdown files."""

    CSS = """
    FilePickerScreen {
        align: center middle;
    }

    #file-picker-dialog {
        width: 80;
        height: 24;
        border: thick $background 80%;
        background: $surface;
    }

    #dialog-title {
        background: $boost;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }

    #dialog-instructions {
        padding: 0 1;
        color: $text-muted;
        text-style: italic;
    }

    FileBrowser {
        height: 1fr;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=False),
    ]

    def __init__(self, start_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_path = start_path

    def compose(self) -> ComposeResult:
        """Create the file picker dialog layout."""
        with Vertical(id="file-picker-dialog"):
            yield Label("📁 Open Markdown File", id="dialog-title")
            yield Label("j/k or ↑/↓=navigate • Enter=select/open • Esc=cancel", id="dialog-instructions")
            yield FileBrowser(start_path=self.start_path)

    def on_key(self, event) -> None:
        """Prevent all key events from bubbling to app."""
        event.stop()

    def on_file_browser_file_selected(
        self, message: FileBrowser.FileSelected
    ) -> None:
        """Handle file selection."""
        message.stop()
        self.dismiss(message.file_path)

    def on_file_browser_selection_cancelled(
        self, message: FileBrowser.SelectionCancelled
    ) -> None:
        """Handle selection cancellation."""
        message.stop()
        self.dismiss(None)


class StatusBar(Static):
    """Status bar showing thread status and notifications."""

    active_threads = reactive(0)
    total_threads = reactive(0)
    notification = reactive("")

    def render(self) -> str:
        """Render the status bar."""
        parts = []

        if self.active_threads > 0:
            parts.append(f"💬 Active threads: {self.active_threads}/{self.total_threads}")
        elif self.total_threads > 0:
            parts.append(f"📝 Total threads: {self.total_threads}")

        if self.notification:
            parts.append(f"📢 {self.notification}")

        if not parts:
            parts.append("Ready • Press 't' on marked line to open thread")

        return " | ".join(parts)


class MarkdownEditorApp(App):
    """A TUI app for editing markdown with Claude."""

    CSS = """
    #main-container {
        height: 1fr;
    }

    #viewer-container {
        width: 100%;
        height: 100%;
        border: solid green;
    }

    #viewer-container.with-panel {
        width: 70%;
    }

    #thread-mode-panel {
        width: 30%;
        height: 100%;
        border: solid yellow;
        display: none;
    }

    #thread-mode-panel.visible {
        display: block;
    }

    #thread-selector-container {
        height: 25%;
        border: solid cyan;
    }

    ThreadSelector {
        height: 100%;
        padding: 1;
    }

    #thread-chat-container {
        height: 75%;
    }

    #comment-container {
        height: 25%;
        border: solid blue;
        display: none;
    }

    #comment-container.visible {
        display: block;
    }

    #edit-container {
        height: 30%;
        border: solid magenta;
        display: none;
    }

    #edit-container.visible {
        display: block;
    }

    #status-bar {
        height: 1;
        background: $boost;
        color: $text;
        padding: 0 1;
    }

    MarkdownViewer {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }

    #viewer-container.with-comment MarkdownViewer {
        height: 70%;
    }

    #viewer-container.with-edit MarkdownViewer {
        height: 70%;
    }

    EditPanel {
        height: 100%;
        padding: 1;
    }

    CommentInput {
        height: 100%;
        padding: 1;
    }

    .section-title {
        background: $surface;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "open_thread", "Open Thread"),
        Binding("a", "add_document_comment", "Document Comment"),
        Binding("r", "reload_file", "Reload File"),
        Binding("ctrl+o", "open_file_picker", "Open File"),
        Binding("ctrl+r", "select_resources", "Select Resources"),
        Binding("ctrl+z", "undo_thread", "Undo"),
        Binding("ctrl+shift+z", "redo_thread", "Redo"),
        Binding("?", "show_help", "Help"),
    ]

    def __init__(self, file_path: str | None):
        super().__init__()
        self.file_path = file_path
        self.config = Config.load()

        # Initialize UI state variables
        self.current_selection: tuple[str, int, int] | None = None
        self.viewer: MarkdownViewer | None = None
        self.comment_input: CommentInput | None = None
        self.edit_panel: EditPanel | None = None
        self.status_bar: StatusBar | None = None
        self.viewer_container = None
        self.comment_container = None
        self.edit_container = None
        self.chat_panel: ThreadChatPanel | None = None
        self.main_container = None
        self.active_thread: CommentThread | None = None
        self.thread_mode = False
        self.edit_mode = False
        self.thread_selector: ThreadSelector | None = None
        self.thread_mode_panel = None

        # File-dependent components (initialized only when file is loaded)
        self.resource_manager: ResourceFileManager | None = None
        self.git_manager: GitManager | None = None
        self.merge_coordinator: MergeCoordinator | None = None
        self.thread_manager: ClaudeThreadManager | None = None
        self.undo_manager: UndoManager | None = None
        self.persistence: ThreadPersistence | None = None

        # Initialize file-dependent components if file path provided
        if file_path:
            self._initialize_file_components()

    def _initialize_file_components(self) -> None:
        """Initialize components that depend on having a file loaded."""
        if not self.file_path:
            return

        # Initialize resource file manager
        self.resource_manager = ResourceFileManager(self.file_path)

        # Get resource files: start with per-file saved resources
        saved_resources = self.resource_manager.get_resources()
        # Fall back to global config resources if no per-file resources
        resource_files = saved_resources if saved_resources else self.config.validate_resource_files()

        # Initialize git manager for version control
        self.git_manager = GitManager(self.file_path)
        self.git_manager.ensure_repo()  # Create .harlowe/.git if needed

        # Initialize merge coordinator for conflict resolution
        self.merge_coordinator = MergeCoordinator(
            git_manager=self.git_manager,
            document_path=Path(self.file_path),
            thread_manager=None  # Will be set after thread_manager is created
        )

        # Initialize thread manager with concurrent execution support
        self.thread_manager = ClaudeThreadManager(
            claude_command=self.config.claude_command,
            file_path=self.file_path,
            resource_files=resource_files,
            merge_coordinator=self.merge_coordinator
        )
        self.thread_manager.set_on_update_callback(self._on_thread_update)

        # Link merge coordinator back to thread manager
        self.merge_coordinator.thread_manager = self.thread_manager

        # Initialize undo manager for git-based undo/redo
        self.undo_manager = UndoManager(
            git_manager=self.git_manager,
            thread_manager=self.thread_manager
        )

        # Initialize thread persistence
        self.persistence = ThreadPersistence(
            self.file_path,
            threads_dir=self.config.threads_dir
        )

        # Load existing threads
        self.thread_manager.threads = self.persistence.load_threads()

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        # Main horizontal container
        with Horizontal(id="main-container"):
            # Left side: Markdown viewer (with optional comment panel)
            with Vertical(id="viewer-container"):
                yield Label("📖 Markdown Viewer (v=visual, a=doc comment, j/k=move, t=thread mode)", classes="section-title")
                self.viewer = MarkdownViewer(self.file_path)
                yield self.viewer

                # Bottom pane: Comment input (for creating new threads)
                with Vertical(id="comment-container"):
                    yield Label("✏️  Comment (Ctrl+J to submit, Esc to cancel)", classes="section-title")
                    self.comment_input = CommentInput()
                    yield self.comment_input

                # Edit panel (for text editing)
                with Vertical(id="edit-container"):
                    self.edit_panel = EditPanel()
                    yield self.edit_panel

            # Right side: Thread mode panel (selector + chat)
            with Vertical(id="thread-mode-panel"):
                # Thread selector (top 20%)
                with Vertical(id="thread-selector-container"):
                    yield Label("🧵 Active threads", id="thread-view-label", classes="section-title")
                    self.thread_selector = ThreadSelector([])
                    yield self.thread_selector

                # Thread chat (bottom 80%)
                with Vertical(id="thread-chat-container"):
                    pass  # Chat panel will be mounted here dynamically

        # Status bar
        self.status_bar = StatusBar(id="status-bar")
        yield self.status_bar

        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount."""
        # Get container references
        self.viewer_container = self.query_one("#viewer-container")
        self.comment_container = self.query_one("#comment-container")
        self.edit_container = self.query_one("#edit-container")
        self.main_container = self.query_one("#main-container")
        self.thread_mode_panel = self.query_one("#thread-mode-panel")

        # If no file loaded, show file picker immediately
        if not self.file_path:
            self.run_worker(self._show_initial_file_picker())
        else:
            # Update status bar
            self._update_status_bar()

            # Focus the viewer initially
            if self.viewer:
                self.viewer.focus()

    async def _show_initial_file_picker(self) -> None:
        """Show file picker at startup when no file is provided."""
        start_path = Path(os.getcwd())
        result = await self.push_screen_wait(FilePickerScreen(start_path))

        if result:
            # File selected - load it
            self._load_file(result)
        else:
            # User cancelled - exit app
            self.exit()

    def _load_file(self, file_path: str) -> None:
        """Load a new file and reinitialize all components."""
        # Update file path
        self.file_path = file_path

        # Initialize file-dependent components
        self._initialize_file_components()

        # Reload viewer with new file
        if self.viewer:
            self.viewer.file_path = file_path
            self.viewer._load_file()
            self.viewer._update_virtual_size()

            # Reset cursor to top of file
            self.viewer.cursor_line = 0

            # Reset visual mode state
            self.viewer.visual_mode = False
            self.viewer.commenting_mode = False

            # Scroll to top
            self.viewer.scroll_to(x=0, y=0, animate=False)

            self.viewer.refresh()
            self.viewer.focus()

        # Update thread selector if it exists
        if self.thread_selector and self.thread_manager:
            self.thread_selector.set_all_threads(self.thread_manager.threads)

        # Update status bar
        self._update_status_bar()

    def show_comment_panel(self) -> None:
        """Show the comment panel and adjust layout."""
        if self.comment_container and self.viewer_container:
            self.comment_container.add_class("visible")
            self.viewer_container.add_class("with-comment")
            if self.comment_input:
                self.comment_input.focus()

    def hide_comment_panel(self) -> None:
        """Hide the comment panel and expand viewer."""
        if self.comment_container and self.viewer_container:
            self.comment_container.remove_class("visible")
            self.viewer_container.remove_class("with-comment")
            if self.viewer:
                self.viewer.focus()

    def show_edit_panel(self, content: str, initial_line: int) -> None:
        """Show the edit panel and adjust layout."""
        if self.edit_container and self.viewer_container and self.edit_panel:
            # Load content into edit panel
            self.edit_panel = EditPanel(content)
            # Mount the new edit panel
            edit_container = self.query_one("#edit-container")
            edit_container.remove_children()
            edit_container.mount(self.edit_panel)

            # Show the container
            self.edit_container.add_class("visible")
            self.viewer_container.add_class("with-edit")
            self.edit_mode = True

            # Scroll to initial line
            self.edit_panel.scroll_to_line(initial_line, suppress_events=True)

            # Focus the edit panel
            self.edit_panel.focus()

    def hide_edit_panel(self) -> None:
        """Hide the edit panel and expand viewer."""
        if self.edit_container and self.viewer_container:
            self.edit_container.remove_class("visible")
            self.viewer_container.remove_class("with-edit")
            self.edit_mode = False
            if self.viewer:
                self.viewer.focus()

    def on_markdown_viewer_selection_made(self, message: MarkdownViewer.SelectionMade) -> None:
        """Handle selection made in viewer."""
        self.current_selection = (message.selected_text, message.line_start, message.line_end)

        # Show comment panel and focus it
        self.show_comment_panel()

        # Update status
        if self.status_bar:
            self.status_bar.notification = f"Selected lines {message.line_start}-{message.line_end}"

    def on_markdown_viewer_viewer_scrolled(self, message: MarkdownViewer.ViewerScrolled) -> None:
        """Handle viewer scroll - sync to editor if in edit mode."""
        if self.edit_mode and self.edit_panel:
            # Scroll editor to match viewer (suppress events to avoid loop)
            self.edit_panel.scroll_to_line(message.line_number, suppress_events=True)

    def on_edit_panel_editor_scrolled(self, message: EditPanel.EditorScrolled) -> None:
        """Handle editor scroll - sync to viewer if in edit mode."""
        if self.edit_mode and self.viewer:
            # Scroll viewer to match editor (suppress events to avoid loop)
            self.viewer.scroll_to_line(message.line_number, suppress_events=True)

    def on_edit_panel_edit_committed(self, message: EditPanel.EditCommitted) -> None:
        """Handle edit commit - save changes to file."""
        try:
            # Write content to file
            with open(self.file_path, 'w') as f:
                f.write(message.content)

            # Reload the viewer to show changes
            if self.viewer:
                self.viewer.reload_file()

            # Hide edit panel
            self.hide_edit_panel()

            # Update status
            if self.status_bar:
                self.status_bar.notification = "Changes saved"

        except Exception as e:
            if self.status_bar:
                self.status_bar.notification = f"Error saving: {str(e)}"

    def on_edit_panel_edit_cancelled(self, message: EditPanel.EditCancelled) -> None:
        """Handle edit cancel - discard changes."""
        # Just hide the panel without saving
        self.hide_edit_panel()

        # Update status
        if self.status_bar:
            self.status_bar.notification = "Editing cancelled"

    def on_comment_input_comment_submitted(self, message: CommentInput.CommentSubmitted) -> None:
        """Handle comment submission - create new thread."""
        if not self.current_selection:
            if self.status_bar:
                self.status_bar.notification = "No text selected!"
            return

        selected_text, line_start, line_end = self.current_selection

        # Create new thread
        thread = self.thread_manager.create_thread(
            selected_text=selected_text,
            comment=message.comment,
            line_start=line_start,
            line_end=line_end
        )

        # Update status
        if self.status_bar:
            self.status_bar.notification = f"Created thread #{str(thread.id)[:8]}"

        # Clear selection, hide panel
        self.current_selection = None
        if self.viewer:
            self.viewer.clear_commenting_mode()
        self.hide_comment_panel()

        # Auto-enter thread mode
        self._enter_thread_mode()

    def _on_thread_update(self, thread: CommentThread) -> None:
        """Callback when a thread is updated."""
        # Save threads
        self.persistence.auto_save(self.thread_manager.threads)

        # Update UI
        self._update_status_bar()

        # Update thread selector if in thread mode
        if self.thread_mode and self.thread_selector:
            self.thread_selector.set_all_threads(self.thread_manager.threads)

        # Update chat panel if this is the active thread
        if self.chat_panel and self.active_thread and thread.id == self.active_thread.id:
            self.chat_panel.update_thread(thread)

        # Show toast notifications for important events
        self._show_thread_notification(thread)

        # Update status based on thread status
        if self.status_bar:
            if thread.status == ThreadStatus.ACTIVE:
                self.status_bar.notification = f"Thread #{str(thread.id)[:8]} active"
            elif thread.status == ThreadStatus.COMPLETED:
                self.status_bar.notification = f"Thread #{str(thread.id)[:8]} closed"
            elif thread.status == ThreadStatus.FAILED:
                self.status_bar.notification = f"Thread #{str(thread.id)[:8]} failed: {thread.error}"

    def _show_thread_notification(self, thread: CommentThread) -> None:
        """Show toast notification for thread events."""
        from .models import MessageRole

        # Don't notify if user is currently viewing this thread
        if self.chat_panel and self.active_thread and thread.id == self.active_thread.id:
            return

        # Don't notify for user's own messages
        if thread.messages and thread.messages[-1].role == MessageRole.USER:
            return

        # Notify for Claude responses
        if thread.status == ThreadStatus.ACTIVE and thread.messages:
            # Check if last message is from assistant
            if thread.messages[-1].role == MessageRole.ASSISTANT:
                if thread.line_start == 0 and thread.line_end == 0:
                    # Document-level thread
                    self.notify(
                        f"Claude responded to document-level thread",
                        title="Thread Response",
                        severity="information",
                        timeout=5.0
                    )
                else:
                    # Line-specific thread
                    self.notify(
                        f"Claude responded to thread on lines {thread.line_start}-{thread.line_end}",
                        title="Thread Response",
                        severity="information",
                        timeout=5.0
                    )

        # Notify for errors
        elif thread.status == ThreadStatus.FAILED:
            self.notify(
                thread.error or "Unknown error occurred",
                title="Thread Error",
                severity="error",
                timeout=7.0
            )

    def action_add_document_comment(self) -> None:
        """Create a document-level comment (line 0)."""
        # Set a special selection for the entire document
        self.current_selection = ("", 0, 0)  # Empty text, line 0 indicates document-level

        # Show comment panel and focus it
        self.show_comment_panel()

        # Update status
        if self.status_bar:
            self.status_bar.notification = "Adding document-level comment"

    def action_open_thread(self) -> None:
        """Toggle thread mode."""
        if self.thread_mode:
            # Exit thread mode
            self._exit_thread_mode()
        else:
            # Enter thread mode
            self._enter_thread_mode()


    def _send_thread_message(self, thread: CommentThread, message: str) -> None:
        """Send a message to a thread."""
        import asyncio
        try:
            asyncio.create_task(self.thread_manager.send_message(thread, message))
        except RuntimeError:
            pass

    def _close_thread(self, thread: CommentThread) -> None:
        """Close a thread."""
        self.thread_manager.close_thread(thread)

        # If we're in thread mode, keep panels open and just clear active thread
        if self.thread_mode:
            # Clear the chat panel if this was the active thread
            if self.active_thread and thread.id == self.active_thread.id:
                if self.chat_panel:
                    self.chat_panel.remove()
                    self.chat_panel = None
                self.active_thread = None

            # Refresh thread selector to update the list
            if self.thread_selector:
                self.thread_selector.set_all_threads(self.thread_manager.threads)
                self.thread_selector.focus()
        else:
            # Not in thread mode - old behavior: close everything
            # Remove chat panel
            if self.chat_panel:
                self.chat_panel.remove()
                self.chat_panel = None

            # Restore viewer width
            if self.viewer_container:
                self.viewer_container.remove_class("with-panel")

            # Clear active thread
            self.active_thread = None

            # Focus viewer
            if self.viewer:
                self.viewer.focus()

    def _reopen_thread(self, thread: CommentThread) -> None:
        """Reopen a closed thread."""
        try:
            self.thread_manager.reopen_thread(thread)

            # Update status
            if self.status_bar:
                self.status_bar.notification = f"Reopened thread #{str(thread.id)[:8]}"

            # If we're in thread mode, refresh selector and switch to ACTIVE view
            if self.thread_mode and self.thread_selector:
                # Switch to ACTIVE view to show the reopened thread
                self.thread_selector.current_view = ThreadViewMode.ACTIVE
                self.thread_selector._apply_view_filter()
                self.thread_selector.post_message(
                    ThreadSelector.ViewChanged(ThreadViewMode.ACTIVE)
                )
        except ValueError as e:
            if self.status_bar:
                self.status_bar.notification = f"Error: {str(e)}"

    def _enter_thread_mode(self) -> None:
        """Enter thread mode - show selector and chat panel."""
        self.thread_mode = True

        # Show thread mode panel
        if self.thread_mode_panel:
            self.thread_mode_panel.add_class("visible")

        # Adjust viewer width
        if self.viewer_container:
            self.viewer_container.add_class("with-panel")

        # Update thread selector with active threads
        if self.thread_selector:
            self.thread_selector.set_all_threads(self.thread_manager.threads)
            self.thread_selector.focus()

            # Auto-select first thread if available (will be filtered by view)
            if self.thread_selector.threads:
                self.thread_selector.move_selection(0)

        # Update status
        if self.status_bar:
            self.status_bar.notification = "Thread mode - select a thread"

    def _exit_thread_mode(self) -> None:
        """Exit thread mode - hide selector and chat panel."""
        self.thread_mode = False

        # Hide thread mode panel
        if self.thread_mode_panel:
            self.thread_mode_panel.remove_class("visible")

        # Restore viewer width
        if self.viewer_container:
            self.viewer_container.remove_class("with-panel")

        # Remove chat panel if any
        if self.chat_panel:
            self.chat_panel.remove()
            self.chat_panel = None

        # Clear active thread
        self.active_thread = None

        # Focus viewer
        if self.viewer:
            self.viewer.focus()

        # Update status
        if self.status_bar:
            self.status_bar.notification = "Exited thread mode"

    def _update_status_bar(self) -> None:
        """Update status bar with thread counts."""
        if not self.status_bar:
            return

        active = len([t for t in self.thread_manager.threads if t.status == ThreadStatus.ACTIVE])
        total = len(self.thread_manager.threads)

        self.status_bar.active_threads = active
        self.status_bar.total_threads = total

    def on_thread_selector_thread_selected(self, message: ThreadSelector.ThreadSelected) -> None:
        """Handle thread selection in thread mode."""
        thread = message.thread

        # Mark thread as read/viewed
        thread.mark_as_viewed()

        # Save the updated timestamp
        self.persistence.auto_save(self.thread_manager.threads)

        # Refresh thread selector to update visual styling
        if self.thread_selector:
            self.thread_selector.refresh()

        # Scroll viewer to thread's line position
        if self.viewer:
            self.viewer.scroll_to_line(thread.line_start)

        # Update or create chat panel
        chat_container = self.query_one("#thread-chat-container")

        # Remove existing chat panel if any
        if self.chat_panel:
            self.chat_panel.remove()

        # Create new chat panel
        self.chat_panel = ThreadChatPanel(
            thread=thread,
            on_send_message=self._send_thread_message,
            on_close_thread=self._close_thread,
            on_reopen_thread=self._reopen_thread
        )

        # Mount to chat container
        chat_container.mount(self.chat_panel)

        # Store active thread
        self.active_thread = thread

        # Update status
        if self.status_bar:
            self.status_bar.notification = f"Viewing thread on lines {thread.line_start}-{thread.line_end}"

    def on_thread_selector_focus_input(self, message: ThreadSelector.FocusInput) -> None:
        """Handle request to focus chat input (when user presses Enter in selector)."""
        if self.chat_panel:
            self.chat_panel.focus_input()

    def on_thread_selector_close_thread(self, message: ThreadSelector.CloseThread) -> None:
        """Handle request to close a thread (when user presses Ctrl+T in selector)."""
        self._close_thread(message.thread)

    def on_thread_selector_reopen_thread(self, message: ThreadSelector.ReopenThread) -> None:
        """Handle request to reopen a closed thread (when user presses Ctrl+T in selector)."""
        self._reopen_thread(message.thread)

    def on_thread_selector_view_changed(self, message: ThreadSelector.ViewChanged) -> None:
        """Handle view mode change - update the label."""
        view_names = {
            ThreadViewMode.ACTIVE: "Active threads",
            ThreadViewMode.RECENT: "Recent threads",
            ThreadViewMode.CLOSED: "Closed threads"
        }
        label = self.query_one("#thread-view-label", Label)
        label.update(f"🧵 {view_names[message.view]}")

    def action_reload_file(self) -> None:
        """Reload the markdown file."""
        if self.viewer:
            new_cursor = self.viewer.reload_file()

            if self.status_bar:
                self.status_bar.notification = f"File reloaded (cursor at line {new_cursor + 1})"

    def action_undo_thread(self) -> None:
        """Undo the current/most recent thread's changes."""
        if not self.undo_manager:
            return

        async def perform_undo():
            # Determine which thread to undo
            thread_to_undo = None

            # Priority 1: If thread selector is visible and has a selection, use that thread
            # (undo_manager will validate if it can be undone)
            if self.thread_mode and self.thread_selector:
                selected_thread = self.thread_selector.get_selected_thread()
                if selected_thread:
                    thread_to_undo = selected_thread

            # Priority 2: Find most recently merged thread
            if not thread_to_undo:
                completed_threads = [t for t in self.thread_manager.threads
                                   if t.status == ThreadStatus.COMPLETED
                                   and not t.metadata.get('reverted', False)]
                if completed_threads:
                    # Sort by updated_at to get most recent
                    thread_to_undo = max(completed_threads, key=lambda t: t.updated_at)

            if thread_to_undo:
                await self.undo_manager.undo_thread(thread_to_undo)

                # Reload file to show reverted changes
                if self.viewer:
                    self.viewer.reload_file()

                if self.status_bar:
                    # Use initial_comment as the thread identifier
                    comment_preview = thread_to_undo.initial_comment[:30]
                    if len(thread_to_undo.initial_comment) > 30:
                        comment_preview += "..."
                    self.status_bar.notification = f"Undoing thread: {comment_preview}"
            else:
                if self.status_bar:
                    self.status_bar.notification = "No thread to undo"

        self.run_worker(perform_undo())

    def action_redo_thread(self) -> None:
        """Redo an undone thread."""
        if not self.undo_manager:
            return

        async def perform_redo():
            # Determine which thread to redo
            thread_to_redo = None

            # Priority 1: If thread selector is visible and has a selection, use that thread
            # (undo_manager will validate if it can be redone)
            if self.thread_mode and self.thread_selector:
                selected_thread = self.thread_selector.get_selected_thread()
                if selected_thread:
                    thread_to_redo = selected_thread

            # Priority 2: Find most recently undone thread
            # (redo_thread will handle this if thread_to_redo is None)

            # Pass the selected thread (or None for auto-select)
            await self.undo_manager.redo_thread(thread_to_redo)

            # Reload file to show re-applied changes
            if self.viewer:
                self.viewer.reload_file()

            if self.status_bar:
                if thread_to_redo:
                    comment_preview = thread_to_redo.initial_comment[:30]
                    if len(thread_to_redo.initial_comment) > 30:
                        comment_preview += "..."
                    self.status_bar.notification = f"Redoing thread: {comment_preview}"
                else:
                    self.status_bar.notification = "Redoing thread"

        self.run_worker(perform_redo())

    def action_open_file_picker(self) -> None:
        """Show file picker to open a different file."""
        async def show_picker():
            # Start from directory of current file if available, otherwise cwd
            if self.file_path:
                start_path = Path(self.file_path).parent
            else:
                start_path = Path(os.getcwd())

            result = await self.push_screen_wait(FilePickerScreen(start_path))

            if result:
                # File selected - load it
                self._load_file(result)

                if self.status_bar:
                    file_name = Path(result).name
                    self.status_bar.notification = f"Opened: {file_name}"

        # Run the picker in a worker
        self.run_worker(show_picker())

    def action_select_resources(self) -> None:
        """Show resource file selection dialog."""
        async def show_dialog():
            # Get available markdown files and currently selected resources
            available_files = self.resource_manager.get_available_markdown_files()
            current_resources = self.resource_manager.get_resources()

            # Show dialog
            result = await self.push_screen_wait(
                ResourceFileScreen(
                    available_files=available_files,
                    initially_selected=current_resources
                )
            )

            # Handle result
            if result is not None:  # None means cancelled
                # Save the selection
                self.resource_manager.set_resources(result)

                # Update thread manager with new resources
                self.thread_manager.resource_files = result

                # Update status
                if self.status_bar:
                    count = len(result)
                    self.status_bar.notification = f"Resource files updated: {count} selected"

        # Run the dialog in a worker
        self.run_worker(show_dialog())

    def action_show_help(self) -> None:
        """Show help dialog."""
        help_text = """
Markdown Editor with Claude Threads

NORMAL MODE (Blue cursor):
  ↑/↓ or j/k      Move up/down
  , or .          Page up/down
  Home/End or g/G Jump to top/bottom
  PgUp/PgDn       Page up/down (alternative)
  v               Enter visual mode
  a               Add document-level comment
  t               Enter thread mode

VISUAL MODE (Yellow selection):
  ↑/↓ or j/k      Expand selection
  Enter           Create comment/thread
  v or Esc        Cancel

COMMENTING MODE (Comment panel visible):
  Type your editing instruction
  Ctrl+J          Submit -> create thread -> opens in Thread mode
  Esc             Cancel

THREAD MODE (Right panel visible):
  ↑/↓ or j/k      Navigate thread list
  ←/→             Switch view (Active/Recent/Closed)
  PgUp/PgDn       Page through threads
  Enter           Focus chat input
  t or Esc        Exit thread mode
  Selected thread chat appears below
  Viewer auto-scrolls to thread location

THREAD CHAT (CLI-style message log):
  Type messages to continue conversation with Claude
  Ctrl+J          Send message
  Ctrl+T          Toggle thread (close active / reopen closed)
  Claude edits file directly using tools
  Typing message in closed thread auto-reopens it

OTHER:
  R               Reload file
  Ctrl+R          Select resource files (context for threads)
  q               Quit
  ?               Show this help
        """
        self.notify(help_text.strip(), timeout=15)

    def on_key(self, event) -> None:
        """Handle global key events."""
        # Handle Esc in thread mode
        if self.thread_mode and event.key == "escape":
            self._exit_thread_mode()
            event.prevent_default()
            return

        # Handle Esc in comment input to cancel commenting
        if self.comment_input and self.comment_input.has_focus and event.key == "escape":
            if self.viewer:
                self.viewer.clear_commenting_mode()
            self.current_selection = None
            self.hide_comment_panel()
            event.prevent_default()
            return

        # Handle Esc in edit mode to cancel editing (handled by EditPanel)
        # Edit panel's on_key handles Escape internally

        # In thread mode, don't handle viewer keys
        if self.thread_mode:
            return

        # Only handle navigation keys if viewer has focus
        if not self.viewer or not self.viewer.has_focus:
            return

        # Arrow keys for navigation (line by line)
        if event.key == "down" or event.key == "j":
            self.viewer.move_cursor(1)
            event.prevent_default()
        elif event.key == "up" or event.key == "k":
            self.viewer.move_cursor(-1)
            event.prevent_default()
        # Simple keys for paging (more reliable than modifier keys)
        elif event.key == "comma" or event.key == ",":
            self.viewer.page_up()
            event.prevent_default()
        elif event.key == "period" or event.key == "." or event.key == "full_stop":
            self.viewer.page_down()
            event.prevent_default()
        # Enter key: toggle visual mode OR capture selection
        elif event.key == "enter":
            if self.viewer.visual_mode:
                self.viewer.capture_selection()  # Capture and show comment panel
            else:
                self.viewer.toggle_visual_mode()  # Enter visual mode
            event.prevent_default()
        elif event.key == "escape":
            if self.viewer.visual_mode:
                self.viewer.cancel_visual_mode()
                event.prevent_default()
        # Edit mode: 'e' key to enter text editing
        elif event.key == "e":
            if not self.edit_mode and not self.viewer.visual_mode and not self.viewer.commenting_mode:
                # Get current document content
                with open(self.file_path, 'r') as f:
                    content = f.read()
                # Get current cursor position
                cursor_line = self.viewer.get_cursor_position() + 1  # Convert to 1-indexed
                # Show edit panel
                self.show_edit_panel(content, cursor_line)
                event.prevent_default()
        # Jump to top/bottom
        elif event.key == "g" or event.key == "home":
            self.viewer.move_to_line(0)
            event.prevent_default()
        elif event.key == "G" or event.key == "end":
            self.viewer.move_to_line(self.viewer.total_lines - 1)
            event.prevent_default()
        # Ctrl+D/U still work for vim users
        elif event.key == "ctrl+d" or event.key == "pagedown":
            self.viewer.page_down()
            event.prevent_default()
        elif event.key == "ctrl+u" or event.key == "pageup":
            self.viewer.page_up()
            event.prevent_default()
