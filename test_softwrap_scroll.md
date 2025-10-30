# Test Soft-Wrap Scrolling

This is line 3 with normal text.

This is line 5 - a very long line that should wrap multiple times when displayed in a narrow terminal window. It contains enough text to demonstrate the soft-wrapping behavior and test whether the 10% dead space scrolling works correctly when lines are wrapped into multiple display lines.

Line 7 is short.

Line 9 is another very long line designed to wrap extensively. When you move the cursor through these wrapped lines, the auto-scroll logic should properly detect when the cursor enters the bottom 10% dead space band and trigger scrolling, rather than allowing the cursor to disappear below the visible viewport.

Line 11 is short.

Line 13 - yet another intentionally verbose line with substantial content that will definitely wrap when shown in a constrained width terminal environment, helping us verify that the coordinate system conversion between original line numbers and display line positions is working correctly.

Line 15 is short.

Line 17 continues the pattern with another extremely long piece of text that wraps multiple times, ensuring we have enough wrapped content to properly test the scrolling behavior throughout the document, not just at the beginning or end.

Line 19 is short.

Line 21 provides more wrapped content to scroll through, demonstrating that the fix handles multiple wrapped sections throughout the document and maintains proper scrolling behavior regardless of cursor position.

Line 23 is short.

Line 25 - final long line to complete our test case, ensuring the bottom of the document also handles soft-wrapped content correctly and the cursor doesn't disappear when approaching the end of the file.

Line 27 is short.
Line 28 is short.
Line 29 is short.
Line 30 is the end.
