# Markdown Editor with Claude Integration

A CLI TUI app for commenting on markdown files and sending those comments to Claude CLI for editing.

## Features

- Split-pane interface: markdown viewer + comment input
- Vim-style visual selection for text passages
- Asynchronous Claude CLI integration (non-blocking)
- Manual review and approval of edits
- Smart refresh that preserves your position
- Serial edit queue to avoid conflicts

## Installation

```bash
pip install -e .
```

## Usage

```bash
md-editor path/to/your/file.md
```

## Configuration

Reference files can be set up using `Ctrl-r` within the editor.

**Note:** Editing `~/.config/md-editor/config.json` directly has been deprecated in favor of the `Ctrl-r` keyboard shortcut.

## Keyboard Shortcuts

### Navigation
- `j/k` or `↑/↓` - Move down/up
- `gg` - Go to top
- `G` - Go to bottom
- `Ctrl+d/u` - Page down/up
- Mouse scroll wheel - Scroll up/down

### Selection
- `Enter` - Enter selection mode
- `j/k` or `↑/↓` - Expand selection
- `Enter` - Capture selection and focus comment box
- `Esc` - Exit visual mode

### Commenting
- `Ctrl-j` - Submit comment to Claude
- `Enter` - New line in comment box
- `Esc` - Return to viewer

### Review
- `r` - Review pending edits
- `a` - Accept edit
- `d` - Reject edit
- `R` - Reload file with accepted edits

## How It Works

1. Navigate the markdown file in the top pane
2. Press `v` to enter visual mode and select text
3. Type your editing instruction in the bottom pane
4. Press Enter to send to Claude (runs in background)
5. Continue working - you'll see pending edit count
6. When edits arrive, press `r` to review
7. Accept/reject edits, then `R` to reload
