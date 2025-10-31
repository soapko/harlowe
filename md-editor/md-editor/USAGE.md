# Markdown Editor Usage Guide

## Installation

```bash
# Navigate to the md-editor directory
cd md-editor

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install the package
pip install -e .
```

## Prerequisites

- Python 3.8 or higher
- Claude CLI installed and configured (`claude` command available)
- Terminal that supports TUI applications

## Basic Usage

```bash
# Launch the editor with a markdown file
md-editor path/to/your-file.md

# Example with the sample file
md-editor sample.md
```

## Configuration

On first run, a default configuration file will be created at:
`~/.config/md-editor/config.json`

Example configuration:

```json
{
  "resource_files": [
    "/path/to/style-guide.md",
    "/path/to/context-file.md"
  ],
  "claude_command": "claude"
}
```

### Configuration Options

- **resource_files**: Array of file paths that will be passed to Claude as context for every edit request
- **claude_command**: The command to invoke Claude CLI (default: "claude")

## Keyboard Shortcuts

### Navigation (in Markdown Viewer)

- `j` - Move cursor down one line
- `k` - Move cursor up one line
- `gg` - Go to top of document
- `G` - Go to bottom of document
- `Ctrl+d` - Page down
- `Ctrl+u` - Page up

### Visual Selection Mode

1. Press `v` to enter visual mode
2. Use `j/k` to expand selection down/up
3. Press `Enter` to capture selection and focus comment input
4. Press `Esc` to cancel visual mode without capturing

### Comment Input

1. After selecting text, type your editing instruction in natural language
2. Press `Ctrl+J` to submit the comment to Claude
3. The edit will process in the background
4. Press `Esc` to return focus to the viewer

### Review and Apply Edits

- `r` - Review completed edits (opens diff viewer)
- `R` - Reload file (refreshes viewer with current file contents)
- In diff viewer:
  - `Accept All` button - Apply all edits to the file
  - `Reject All` button - Discard all edits
  - `Close` button - Close without applying

### Other

- `?` - Show help dialog
- `q` - Quit application

## Workflow Example

1. **Launch the app**:
   ```bash
   md-editor my-document.md
   ```

2. **Navigate to section** you want to edit:
   - Use `j/k` to move line by line
   - Use `Ctrl+d/u` to page through document

3. **Select text**:
   - Press `v` to enter visual mode
   - Expand selection with `j/k`
   - Press `Enter` when done

4. **Add editing instruction**:
   - Type natural language instruction (e.g., "make this more concise")
   - Press `Ctrl+J` to submit

5. **Continue working**:
   - The edit processes asynchronously in background
   - Status bar shows pending edit count
   - You can continue selecting and commenting

6. **Review edits** when notified:
   - Press `r` to open diff viewer
   - See original vs edited text for each change
   - Accept all, reject all, or close

7. **Apply changes**:
   - If you accepted edits, press `R` to reload the file
   - Your cursor position is preserved (smart refresh)

## Tips

### Natural Language Instructions

The app sends your comments as natural language instructions to Claude. Examples:

- "Fix grammar and spelling errors"
- "Make this paragraph more concise"
- "Rewrite this in a formal tone"
- "Add more details and examples"
- "Simplify this explanation"
- "Convert this to a bullet list"

### Resource Files

Add frequently referenced files to your config:

```json
{
  "resource_files": [
    "~/docs/style-guide.md",
    "~/docs/terminology.md"
  ]
}
```

These files are passed to Claude with every request, providing consistent context.

### Serial Processing

Edits are processed serially (one at a time) to avoid conflicts. If you submit multiple edits:
- They queue up
- Process in order
- Status bar shows pending count
- You're notified as each completes

### Smart Refresh

When you reload the file (`R`):
- File content updates with applied edits
- Cursor position is preserved approximately
- Line numbers adjust automatically
- You don't lose your place in the document

## Troubleshooting

### "Command not found: claude"

Make sure Claude CLI is installed and the `claude` command is available in your PATH.

### Edits failing

Check:
1. Claude CLI is properly configured
2. You have API access
3. Resource files in config exist and are readable
4. Claude CLI output in error messages

### TUI rendering issues

Some terminals may not support all TUI features. Try:
- Using a modern terminal (iTerm2, Alacritty, Windows Terminal)
- Checking terminal color support
- Resizing the terminal window

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=md_editor
```
