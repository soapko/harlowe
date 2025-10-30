#!/usr/bin/env python3
"""Test script for cursor display position calculation."""

import sys
sys.path.insert(0, '/Users/karl/.local/pipx/venvs/harlowe/lib/python3.14/site-packages')

from md_editor.markdown_viewer import MarkdownViewer

# Create a viewer with the test file
viewer = MarkdownViewer('/Users/karl/Documents/_Projects/harlowe/test_softwrap_scroll.md')

# Force wrapping with a specific width
viewer._wrap_lines(60)

print("Soft-Wrap Scrolling Test")
print("=" * 60)
print(f"Total original lines: {viewer.total_lines}")
print(f"Total wrapped lines: {len(viewer.wrapped_lines)}")
print()

# Show wrapped line mapping
print("Wrapped line mapping (first 20):")
for idx, (orig_idx, text) in enumerate(viewer.wrapped_lines[:20]):
    truncated = text[:50] + "..." if len(text) > 50 else text
    print(f"  Display {idx:2d} -> Original {orig_idx:2d}: {truncated}")
print()

# Test cursor position conversion
test_positions = [0, 5, 9, 13, 17, 21, 25, 29]
print("Cursor position conversions:")
for orig_line in test_positions:
    viewer.cursor_line = orig_line
    display_pos = viewer._get_cursor_display_position()
    print(f"  Original line {orig_line:2d} -> Display position {display_pos:2d}")
print()

# Verify correctness
print("Verification:")
for orig_line in [5, 9, 13]:
    viewer.cursor_line = orig_line
    display_pos = viewer._get_cursor_display_position()
    actual_orig_line = viewer.wrapped_lines[display_pos][0]

    status = "✓" if actual_orig_line == orig_line else "✗"
    print(f"  {status} Line {orig_line}: display_pos={display_pos}, wrapped_lines[{display_pos}][0]={actual_orig_line}")

print()
print("Test complete!")
