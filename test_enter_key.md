# Test File for Enter Key Visual Mode

Line 1: First line
Line 2: Second line
Line 3: Third line
Line 4: Fourth line
Line 5: Fifth line

## Test Instructions

1. Press Enter in Normal mode → Should enter Visual mode (yellow highlight)
2. Press j or k to move cursor → Selection should expand
3. Press Enter again → Should capture selection and open comment panel
4. Press Esc → Should cancel and return to Normal mode

## Expected Behavior

- Enter key in Normal mode: Enters Visual selection mode
- Enter key in Visual mode: Captures selection and enters Commenting mode
- 'v' key: No longer bound (should do nothing)
