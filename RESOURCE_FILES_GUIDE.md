# Resource Files Feature - Quick Guide

## What are Resource Files?

Resource files are additional markdown files that you want Claude to reference when working on a specific document. They provide context, style guides, or related information that helps Claude give better responses.

## How to Use

### Opening the Selector
1. Press `Ctrl+P` to open the command palette
2. Type "resource" or "select"
3. Select "Select Resource Files" from the list
4. Press Enter to open the resource file selector dialog

### Selecting Files
- **Navigate:** Use `j`/`k` or arrow keys to move up/down
- **Toggle:** Press `Space` to check/uncheck a file
- **Confirm:** Press `Enter` to save your selection
- **Cancel:** Press `Esc` to close without saving

### Navigation Shortcuts
- `g` - Jump to top of list
- `G` - Jump to bottom of list
- `Ctrl+d` - Page down (5 lines)
- `Ctrl+u` - Page up (5 lines)

## Example Use Cases

### 1. Style Guide
Select `STYLE_GUIDE.md` when editing blog posts to maintain consistent tone and formatting.

### 2. API Documentation
Select `API_REFERENCE.md` when writing code examples that use your API.

### 3. Related Documents
When editing `chapter-3.md`, select `chapter-1.md` and `chapter-2.md` for continuity.

### 4. Project Context
Select `PROJECT_OVERVIEW.md` when working on any project file for consistent context.

## How It Works

1. **Per-File Selection:** Each markdown file remembers its own resource files
2. **Automatic Loading:** When you reopen a file, resources are automatically loaded
3. **Thread Context:** When you create a thread, selected resources are included in Claude's prompt
4. **Persistent:** Selections saved to `.md-editor-resources.json` in your project directory

## Example Workflow

```bash
# 1. Open your document
harlowe blog-post.md

# 2. Select resources (Ctrl+P)
#    - Check: STYLE_GUIDE.md
#    - Check: TEMPLATE.md
#    - Press Enter

# 3. Create a thread (v, select text, Enter)
#    Type: "Rewrite this section to match our style"
#    Press Ctrl+J

# 4. Claude responds with context from both resource files
```

## Tips

- **Be Selective:** Only include relevant resources (2-4 is usually enough)
- **Keep It Updated:** If you rename/delete resource files, remove them from selection
- **Test Context:** Try with and without resources to see the difference in Claude's responses
- **Project-Local:** Each project can have its own `.md-editor-resources.json`

## Where Files Are Saved

Resource selections are saved in:
```
/path/to/your/project/.md-editor-resources.json
```

This file is project-local and can be:
- Added to `.gitignore` if it's personal preference
- Committed to git if you want to share it with your team

## Troubleshooting

**Dialog shows "No markdown files found"**
- This happens when your markdown file is alone in its directory
- Create or move related markdown files to the same directory

**Previously selected file not showing**
- The file may have been deleted or moved
- Select it again or remove it from selection

**Resources not affecting Claude responses**
- Verify files are actually checked (press Ctrl+P to confirm)
- Check that resource files contain relevant content
- Try creating a new thread to test

## Advanced: Manual Editing

You can manually edit `.md-editor-resources.json`:

```json
{
  "/full/path/to/document.md": [
    "/full/path/to/resource1.md",
    "/full/path/to/resource2.md"
  ]
}
```

Use absolute paths only. Relative paths are not supported.
