# Resource File Selector Implementation Summary

## Overview

Implemented a Ctrl+P command palette feature that allows users to select resource files (other markdown files in the same directory) to include as context when creating Claude threads. The selection is persisted per-markdown-file in a project-local `.md-editor-resources.json` file.

---

## What Was Implemented

### 1. **ResourceFileManager** (`resource_file_manager.py`)
A persistence layer that manages resource file associations.

**Key Features:**
- Loads/saves `.md-editor-resources.json` from the same directory as the markdown file
- Schema: `{"/absolute/path/to/doc.md": ["file1.md", "file2.md"]}`
- Discovers available markdown files in the current directory
- Filters out non-existent files automatically
- Removes entries when all resources are cleared

**Methods:**
- `get_resources()` - Get resource files for current markdown file
- `set_resources(files)` - Save resource file selection
- `get_available_markdown_files()` - Discover markdown files in directory

### 2. **ResourceFileSelector** (`resource_file_selector.py`)
A scrollable list widget with checkbox-style selection.

**Key Features:**
- Displays markdown files with checkboxes: `[ ]` or `[✓]`
- Multi-select support (Space to toggle)
- Vim-style navigation (j/k, g/G, Ctrl+d/u)
- Shows currently selected files pre-checked
- Cursor/selection highlighting (blue background)

**Keybindings:**
- `j` / `↓` - Move down
- `k` / `↑` - Move up
- `Space` - Toggle checkbox
- `Enter` - Confirm selection
- `Esc` - Cancel
- `g` / `G` - Jump to top/bottom
- `Ctrl+d` / `Ctrl+u` - Page down/up

### 3. **ResourceFileScreen** (`app.py`)
A modal Screen overlay for the resource file selector dialog.

**Design:**
- Centered modal dialog (80 chars wide, 24 lines tall)
- Title: "📎 Select Resource Files"
- Instructions line showing available keys
- Contains ResourceFileSelector widget
- Dismisses with result or None (on cancel)

### 4. **App Integration** (`app.py`)
Integrated resource file selection into the main application.

**Changes:**
- Added `Ctrl+P` keybinding → `action_select_resources`
- Initialize `ResourceFileManager` on app startup
- Load saved resources for current file (falls back to global config if none)
- Pass resources to `ClaudeThreadManager` for thread creation
- Update help text to document Ctrl+P feature

**Resource Loading Priority:**
1. Per-file saved resources (from `.md-editor-resources.json`)
2. Global config resources (from `~/.config/md-editor/config.json`)

---

## Files Created

1. `/Users/karl/Documents/_Projects/harlowe/md-editor/md-editor/src/md_editor/resource_file_manager.py` (115 lines)
2. `/Users/karl/Documents/_Projects/harlowe/md-editor/md-editor/src/md_editor/resource_file_selector.py` (198 lines)

---

## Files Modified

1. `/Users/karl/Documents/_Projects/harlowe/md-editor/md-editor/src/md_editor/app.py`
   - Added imports for new components
   - Added `ResourceFileScreen` modal class
   - Added `resource_manager` initialization in `__init__`
   - Updated resource loading logic to prioritize per-file resources
   - Added `action_select_resources()` async action
   - Added `Ctrl+P` keybinding
   - Updated help text

---

## How It Works

### Workflow

1. **User presses Ctrl+P**
   - `action_select_resources()` is called
   - Gets available markdown files from current directory
   - Gets currently saved resources for this file
   - Opens `ResourceFileScreen` modal

2. **User selects files in dialog**
   - Navigate with j/k
   - Toggle checkboxes with Space
   - Confirm with Enter (or cancel with Esc)

3. **On confirmation**
   - `ResourceFileManager.set_resources()` saves selection to JSON
   - `ClaudeThreadManager.resource_files` is updated
   - Status bar shows confirmation message

4. **When creating a thread**
   - `ClaudeThreadManager` includes resource file content in prompt
   - Uses existing mechanism: `_build_initial_prompt()` already reads `self.resource_files`
   - Content is embedded in the prompt under "REFERENCE DOCUMENTATION" section

5. **On next app launch**
   - `ResourceFileManager` loads saved resources for current file
   - Selection is pre-populated if user presses Ctrl+P again

---

## Integration with Existing Code

The implementation integrates seamlessly with existing architecture:

### Existing Pattern: Resource Files
- `ClaudeThreadManager` already supported `resource_files` parameter
- `_build_initial_prompt()` already embedded resource content in prompts
- We just added a UI to manage these dynamically instead of hardcoding in config

### Existing Pattern: Modal Dialogs
- Textual's `Screen` system for modals (push/dismiss)
- Similar to how thread chat panel is dynamically mounted

### Existing Pattern: Keyboard Navigation
- Followed same vim-style keys as `ThreadSelector` and `MarkdownViewer`
- Consistent j/k, g/G, Ctrl+d/u navigation

### Existing Pattern: Persistence
- Similar to `ThreadPersistence` using JSON files
- Project-local storage like thread files

---

## Testing

### Automated Tests ✓
- Persistence: saving, loading, clearing resources
- File discovery: finding markdown files in directory
- Filtering: removing non-existent files
- UI components: initialization and imports
- App integration: resource_manager, keybindings, actions

### Manual Tests Required
- Interactive TUI behavior (see MANUAL_TEST_PLAN.md)
- Dialog appearance and navigation
- Checkbox toggling and visual feedback
- Thread creation with resource context
- Per-file persistence across app restarts
- Edge cases (empty directory, deleted files, many files)

**Status:** Automated tests passed. Manual testing required for interactive validation.

---

## User Benefits

1. **Dynamic Context Management**
   - No need to edit config.json
   - Select relevant context per document
   - Different resources for different documents

2. **Persistent Preferences**
   - Selection saved automatically
   - Restored when reopening file
   - Project-local, not global

3. **Better Claude Responses**
   - Include relevant documentation
   - Reference related markdown files
   - Provide consistent style guides

4. **Easy to Use**
   - Simple Ctrl+P shortcut
   - Checkbox interface (familiar UX)
   - Vim-style navigation

---

## Technical Details

### Data Storage Format

**File:** `.md-editor-resources.json` (in same directory as markdown files)

```json
{
  "/absolute/path/to/document.md": [
    "/absolute/path/to/resource1.md",
    "/absolute/path/to/resource2.md"
  ],
  "/absolute/path/to/another.md": [
    "/absolute/path/to/resource3.md"
  ]
}
```

### Claude Prompt Format

When resources are selected, they're embedded in the initial prompt:

```
REFERENCE DOCUMENTATION:

--- resource1.md ---
[content of resource1.md]
--- End of reference ---

--- resource2.md ---
[content of resource2.md]
--- End of reference ---


You are assisting with editing a markdown file in Harlowe...
[rest of prompt]
```

### Performance Considerations

- File discovery: Uses `Path.glob("*.md")` - fast for typical directories
- Resource loading: Only reads files when creating threads (lazy)
- JSON persistence: Small file, quick writes
- UI rendering: Textual handles efficiently with virtual scrolling

---

## Future Enhancements (Not Implemented)

Possible improvements for later:

1. **Subdirectory search** - Recursive file discovery
2. **File preview** - Show snippet of selected resource
3. **Resource categories** - Group resources by type
4. **Quick toggle** - Keyboard shortcut to toggle common resources
5. **Search/filter** - Type to filter file list
6. **Resource indicators** - Show active resources in status bar
7. **Non-markdown files** - Support .txt, .json, etc.

---

## Git Integration Notes

Consider adding to `.gitignore`:
```
.md-editor-resources.json
```

This is a personal preference file, similar to `.vscode/settings.json` or editor-specific configs.

---

## Conclusion

The resource file selector feature is fully implemented and tested at the code level. The implementation follows existing patterns in the codebase, integrates cleanly with the thread creation system, and provides a user-friendly interface for managing per-file context.

**Status:** Ready for manual testing and user validation.
