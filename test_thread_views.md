# Test File for Thread View Toggling

## Instructions for Testing

1. **Create Active Threads**:
   - Press Enter on line 10 to enter visual mode
   - Move down with j/k to select multiple lines
   - Press Enter to capture and create a comment
   - Submit with Ctrl+J to create an ACTIVE thread

2. **Create More Threads**:
   - Repeat process on lines 20 and 30
   - Create at least 3 active threads

3. **Test View Switching**:
   - Press 't' to enter Thread mode
   - Press → (right arrow) to cycle: Active → Recent → Closed
   - Press ← (left arrow) to cycle backwards: Closed → Recent → Active
   - Verify looping works (Closed → Active when pressing right)

4. **Close Some Threads**:
   - Select a thread in Active view
   - Press Enter to focus chat
   - Press Ctrl+T to close the thread
   - Switch to Closed view (→ →) to see it there

5. **Test Recent View**:
   - Switch to Recent view
   - All threads should appear sorted by most recent activity
   - Add a message to an older thread
   - Switch views and back - it should now be at top of Recent

## Test Lines (Use these for creating threads)

Line 10: First test line for thread creation
Line 11: Second line of first thread
Line 12: Third line of first thread

Line 20: Second test thread starts here
Line 21: More content for second thread
Line 22: End of second thread

Line 30: Third test thread location
Line 31: Additional content here
Line 32: Final line of third thread

## Expected Behavior

- **Active View**: Shows only threads with status ACTIVE
- **Recent View**: Shows ALL threads sorted by updated_at (most recent first)
- **Closed View**: Shows only threads with status COMPLETED
- **Arrow Keys**: Loop through views continuously
- **Selection**: Resets to top (index 0) when switching views
- **Empty States**: Different messages for each view type
