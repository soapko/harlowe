# Manual Test Plan: Resource File Selector Feature

## Test Date: 2025-10-28

## Feature Description
A Ctrl+P command palette that allows selecting resource files (other markdown files in the same directory) to include as context when creating Claude threads. Selection is persisted per-markdown-file in `.md-editor-resources.json`.

---

## Automated Tests - PASSED ✓

### Test 1: ResourceFileManager Persistence
**Status: ✓ PASSED**
- [x] Initializes correctly with a markdown file path
- [x] Discovers available markdown files in directory
- [x] Saves selected resources to `.md-editor-resources.json`
- [x] Loads saved resources on new instance
- [x] Removes entry when resources are cleared
- [x] Filters out non-existent files

### Test 2: UI Component Integration
**Status: ✓ PASSED**
- [x] ResourceFileManager imports correctly
- [x] ResourceFileSelector imports correctly
- [x] ResourceFileScreen imports correctly
- [x] MarkdownEditorApp initializes with resource_manager
- [x] action_select_resources method exists
- [x] Ctrl+P keybinding is registered

---

## Manual Tests - TO BE PERFORMED

### Test 3: Opening Resource File Selector Dialog
**Steps:**
1. Run: `harlowe test.md`
2. Press `Ctrl+P`

**Expected Results:**
- [ ] Dialog appears centered on screen
- [ ] Dialog title shows "📎 Select Resource Files"
- [ ] Instructions show "Space=toggle • Enter=confirm • Esc=cancel"
- [ ] List shows all markdown files except test.md:
  - [ ] CLAUDE.md
  - [ ] test_enter_key.md
  - [ ] test_softwrap_scroll.md
  - [ ] test_thread_mode.md
  - [ ] test_thread_views.md
  - [ ] test_wrap.md
- [ ] All files start unchecked: `[ ]`
- [ ] First file is highlighted (blue background)

---

### Test 4: Navigation in Selector
**Steps:**
1. Open dialog with `Ctrl+P`
2. Press `j` or `↓` key several times
3. Press `k` or `↑` key several times
4. Press `Ctrl+D` (page down)
5. Press `Ctrl+U` (page up)
6. Press `g` (jump to top)
7. Press `G` (jump to bottom)

**Expected Results:**
- [ ] Selection cursor moves down with j/↓
- [ ] Selection cursor moves up with k/↑
- [ ] Cursor moves 5 lines down with Ctrl+D
- [ ] Cursor moves 5 lines up with Ctrl+U
- [ ] Cursor jumps to first file with g
- [ ] Cursor jumps to last file with G
- [ ] Blue highlight follows cursor position
- [ ] Scrolling works if list is longer than viewport

---

### Test 5: Toggling Checkboxes
**Steps:**
1. Open dialog with `Ctrl+P`
2. Navigate to "CLAUDE.md" file
3. Press `Space`
4. Navigate to "test_wrap.md" file
5. Press `Space`
6. Navigate back to "CLAUDE.md"
7. Press `Space` again

**Expected Results:**
- [ ] CLAUDE.md checkbox changes from `[ ]` to `[✓]` after first Space
- [ ] test_wrap.md checkbox changes to `[✓]` after Space
- [ ] CLAUDE.md checkbox changes back to `[ ]` after second Space
- [ ] Checkboxes update immediately
- [ ] Multiple files can be checked simultaneously

---

### Test 6: Confirming Selection
**Steps:**
1. Open dialog with `Ctrl+P`
2. Select 2 files (e.g., CLAUDE.md and test_wrap.md) using Space
3. Press `Enter`

**Expected Results:**
- [ ] Dialog closes immediately
- [ ] Status bar shows "Resource files updated: 2 selected"
- [ ] File `.md-editor-resources.json` is created in project directory
- [ ] JSON file contains correct mapping for test.md

**Verification:**
```bash
cat /Users/karl/Documents/_Projects/harlowe/.md-editor-resources.json
```
Should show:
```json
{
  "/Users/karl/Documents/_Projects/harlowe/test.md": [
    "/Users/karl/Documents/_Projects/harlowe/CLAUDE.md",
    "/Users/karl/Documents/_Projects/harlowe/test_wrap.md"
  ]
}
```

---

### Test 7: Cancelling Selection
**Steps:**
1. Open dialog with `Ctrl+P`
2. Select some files with Space
3. Press `Esc`

**Expected Results:**
- [ ] Dialog closes immediately
- [ ] No changes are saved
- [ ] Previous selection (if any) remains unchanged
- [ ] App returns to normal viewing mode

---

### Test 8: Persistence - Reopening Dialog
**Steps:**
1. Select 2 files and confirm (Test 6)
2. Close the app
3. Reopen: `harlowe test.md`
4. Press `Ctrl+P`

**Expected Results:**
- [ ] Dialog opens
- [ ] Previously selected files are pre-checked: `[✓]`
- [ ] Other files remain unchecked: `[ ]`
- [ ] Selection matches what was saved

---

### Test 9: Thread Creation with Resources
**Steps:**
1. Select CLAUDE.md as resource file (Ctrl+P, Space, Enter)
2. In viewer, press `v` to enter visual mode
3. Select a few lines
4. Press `Enter` to create comment
5. Type: "Summarize this section"
6. Press `Ctrl+J` to create thread
7. Wait for Claude response

**Expected Results:**
- [ ] Thread is created and enters thread mode
- [ ] Claude's prompt includes CLAUDE.md content (check logs if possible)
- [ ] Claude responds based on context from resource file
- [ ] Resource file content is included in initial prompt

**Note:** You may need to check the actual Claude CLI command being executed. The thread_manager should include resource files in the prompt.

---

### Test 10: Different Files, Different Resources
**Steps:**
1. Open test.md: `harlowe test.md`
2. Select CLAUDE.md as resource (Ctrl+P)
3. Close app
4. Open test_wrap.md: `harlowe test_wrap.md`
5. Press Ctrl+P

**Expected Results:**
- [ ] test_wrap.md shows no resources selected initially
- [ ] This proves resources are per-file, not global

**Then:**
6. Select test.md as resource for test_wrap.md
7. Confirm selection
8. Verify `.md-editor-resources.json` now has two entries:

```json
{
  "/Users/karl/.../test.md": [...],
  "/Users/karl/.../test_wrap.md": ["/Users/karl/.../test.md"]
}
```

---

### Test 11: Clearing Resources
**Steps:**
1. Open file with existing resources: `harlowe test.md`
2. Press `Ctrl+P` (should show checked files)
3. Press `Space` on each checked file to uncheck all
4. Press `Enter` to confirm
5. Close app
6. Check JSON file

**Expected Results:**
- [ ] All checkboxes can be unchecked
- [ ] Empty selection is accepted
- [ ] Status bar shows "Resource files updated: 0 selected"
- [ ] JSON file either removes the entry or shows empty array
- [ ] Reopening dialog shows no files checked

---

### Test 12: Help Text Update
**Steps:**
1. Open app: `harlowe test.md`
2. Press `?` to show help

**Expected Results:**
- [ ] Help text includes new line:
  ```
  Ctrl+P          Select resource files (context for threads)
  ```
- [ ] Help text is clear and understandable

---

### Test 13: Edge Cases

#### Test 13a: Empty Directory
**Steps:**
1. Create new directory with single markdown file
2. Open that file with harlowe
3. Press `Ctrl+P`

**Expected Results:**
- [ ] Dialog shows "No markdown files found in directory"
- [ ] Can still press Esc to close

#### Test 13b: Many Files
**Steps:**
1. Create directory with 20+ markdown files
2. Open one with harlowe
3. Press `Ctrl+P`

**Expected Results:**
- [ ] Dialog shows scrollable list
- [ ] All files are accessible via scrolling
- [ ] Performance is acceptable

#### Test 13c: File Deleted After Selection
**Steps:**
1. Select a resource file and save
2. Close app
3. Delete the selected resource file
4. Reopen app
5. Press `Ctrl+P`

**Expected Results:**
- [ ] Deleted file is not shown in list
- [ ] Deleted file is automatically filtered from saved selection
- [ ] No errors occur

---

## Test Execution Log

### Tester: _______________
### Date: _______________

| Test # | Status | Notes |
|--------|--------|-------|
| 1      | ✓      | Automated - passed |
| 2      | ✓      | Automated - passed |
| 3      |        |  |
| 4      |        |  |
| 5      |        |  |
| 6      |        |  |
| 7      |        |  |
| 8      |        |  |
| 9      |        |  |
| 10     |        |  |
| 11     |        |  |
| 12     |        |  |
| 13a    |        |  |
| 13b    |        |  |
| 13c    |        |  |

---

## Known Issues

None currently known. Add any issues discovered during manual testing here.

---

## Notes

- The feature uses Textual's Screen system for modal dialogs
- Resource files are saved in `.md-editor-resources.json` in the same directory as the markdown files
- This file should be added to `.gitignore` if desired (local preference)
- Resource files are included in Claude prompts via the existing `resource_files` mechanism in ClaudeThreadManager
