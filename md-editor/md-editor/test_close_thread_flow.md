# Test: Ctrl+T Thread Closing Workflow

## Changes Made:

1. **ThreadSelector** (`thread_selector.py`):
   - Added `CloseThread` message class
   - Added Ctrl+T key handler that posts CloseThread message with selected thread

2. **MarkdownEditorApp** (`app.py`):
   - Added `on_thread_selector_close_thread()` handler
   - Modified `_close_thread()` to check if in thread mode:
     - **In thread mode**: Keep panels open, refresh selector, refocus selector
     - **Not in thread mode**: Old behavior (close everything)

## Expected Behavior:

### In Thread Mode (Right panel visible):
1. Navigate thread selector with j/k keys
2. Press Ctrl+T on any selected thread
3. Thread is closed and marked as completed
4. Thread selector refreshes to show updated list
5. Selector remains focused (ready for next Ctrl+T)
6. Panels stay open - no need to re-enter thread mode

### In Chat Panel (Inside a thread):
1. Press Ctrl+T while in chat input
2. Current thread is closed
3. Since we're in thread mode, panels stay open
4. Focus returns to thread selector

## Test Workflow:

```
1. Open file with `harlowe test.md`
2. Create multiple threads (select text with 'v', add comment)
3. Press 't' to enter thread mode
4. Use j/k to navigate threads
5. Press Ctrl+T repeatedly to close threads one by one
6. Observe: Panels stay open, can keep closing threads rapidly
```

## Key Files Modified:
- src/md_editor/thread_selector.py (+9 lines)
- src/md_editor/app.py (+22 lines, modified _close_thread logic)
