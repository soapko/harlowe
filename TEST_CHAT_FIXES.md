# Manual Test Plan: Chat Message Display & Thread Indicators

## Summary of Changes

This test plan verifies two fixes to the chat/thread system:

1. **Fix 1**: User messages now appear immediately in chat window when submitted
2. **Fix 2**: Threads show "⏳" indicator when awaiting Claude response

---

## Modified Files

- `md-editor/src/md_editor/models.py` - Added `awaiting_response` field to CommentThread
- `md-editor/src/md_editor/thread_manager.py` - User message added immediately, awaiting flag set
- `md-editor/src/md_editor/thread_selector.py` - Added "⏳" indicator and cyan styling for awaiting threads

---

## Test Procedure

### Setup
1. Launch harlowe with a test file:
   ```bash
   harlowe test_thread_mode.md
   ```

2. Enter Visual mode (Shift+V) and select some text

3. Press Ctrl+J to create a new thread comment

---

### Test 1: Immediate Message Display

**Objective**: Verify that user messages appear immediately in the chat window

**Steps**:
1. In the thread chat panel, type a message in the input area
2. Press Ctrl+J to send the message
3. **OBSERVE**: The user message should immediately appear in the chat log above
4. Wait for Claude to respond
5. **OBSERVE**: Claude's response should appear below the user message

**Expected Results**:
- ✅ User message appears in chat log immediately after pressing Ctrl+J
- ✅ No delay or "blank" period in the chat window
- ✅ Chat log scrolls to show the new user message
- ✅ Claude's response appears after processing is complete

**Previous Behavior** (bug):
- ❌ User message would disappear from input
- ❌ Nothing would show in chat log
- ❌ User would wait with no feedback
- ❌ Both user message and Claude response would appear together after Claude finished

---

### Test 2: Awaiting Response Indicator

**Objective**: Verify that threads show "⏳" indicator when awaiting Claude's response

**Steps**:
1. With a thread open, send a message (Ctrl+J)
2. **IMMEDIATELY** look at the thread selector panel (left side)
3. **OBSERVE**: The current thread should show "⏳" indicator
4. **OBSERVE**: The thread line should be cyan/blue colored
5. Wait for Claude to respond
6. **OBSERVE**: After response arrives, "⏳" should disappear
7. If thread has unread updates, it should show "*" instead

**Expected Results**:
- ✅ "⏳" indicator appears immediately when message is sent
- ✅ Thread line is styled in cyan color (bold)
- ✅ "⏳" takes priority over "*" (unread indicator)
- ✅ "⏳" disappears after Claude responds
- ✅ If viewed thread has unread, it shows "*" after response

**Visual Indicators**:
- `⏳ ` = Awaiting Claude response (cyan, bold)
- `* ` = Unread updates (yellow, bold)
- `  ` = No activity (default)

---

### Test 3: Multiple Threads

**Objective**: Verify indicators work correctly with multiple threads

**Steps**:
1. Create Thread A and send a message
2. While Thread A is awaiting response, switch to Thread B (create if needed)
3. Send a message in Thread B
4. **OBSERVE**: Both threads should show "⏳" in the thread selector
5. Wait for responses to arrive
6. **OBSERVE**: Indicators should clear as responses arrive

**Expected Results**:
- ✅ Multiple threads can show "⏳" simultaneously
- ✅ Each thread's indicator updates independently
- ✅ Switching between threads doesn't affect indicators
- ✅ Indicators persist across thread switches

---

### Test 4: Error Handling

**Objective**: Verify awaiting indicator clears even if Claude errors

**Steps**:
1. Send a message that might cause an error (or kill the process mid-execution)
2. **OBSERVE**: "⏳" indicator should still appear
3. Wait for error or timeout
4. **OBSERVE**: "⏳" should clear when error is reported

**Expected Results**:
- ✅ "⏳" appears even if request will fail
- ✅ "⏳" clears when error occurs
- ✅ Thread can still be used after error

---

## Verification Checklist

### Issue 1: Immediate Message Display
- [ ] User message appears instantly in chat log
- [ ] No waiting period with blank chat
- [ ] Message doesn't disappear before appearing
- [ ] Chat log auto-scrolls to new message
- [ ] Multiple messages in a row all appear immediately

### Issue 2: Awaiting Indicator
- [ ] "⏳" appears when message is sent
- [ ] Thread is styled in cyan color
- [ ] "⏳" disappears after Claude responds
- [ ] "⏳" takes priority over "*" (unread)
- [ ] Works with multiple threads simultaneously
- [ ] Indicator clears on error

---

## Notes for Testing

- The "⏳" character is an hourglass emoji that should render in most terminals
- Cyan color may vary depending on terminal color scheme
- If Claude CLI is slow to respond, this is a good opportunity to observe the indicators
- You can test rapid succession by sending multiple messages quickly

---

## Rollback Instructions

If issues are found, revert these commits:
```bash
cd /Users/karl/Documents/_Projects/harlowe/md-editor/md-editor
git log --oneline -5  # Find commit hash
git revert <commit-hash>
pipx reinstall harlowe
```

---

## Code Changes Summary

### models.py:76
Added field:
```python
awaiting_response: bool = False  # True when waiting for Claude to respond
```

### thread_manager.py:119-122
User message added immediately:
```python
# Add user message immediately so it shows in UI
thread.add_message(MessageRole.USER, message)
thread.awaiting_response = True
self._notify_update(thread)
```

### thread_manager.py:142-143
Flag cleared after response:
```python
thread.add_message(MessageRole.ASSISTANT, response)
thread.awaiting_response = False
```

### thread_selector.py:142-147
Indicator logic:
```python
if is_awaiting:
    status_prefix = "⏳ "
elif is_unread:
    status_prefix = "* "
else:
    status_prefix = "  "
```
