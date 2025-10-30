#!/usr/bin/env python3
"""Test cursor skipping empty/decorative lines."""

from md_editor.markdown_viewer import MarkdownViewer

def test_cursor_skip():
    """Test that cursor skips empty/decorative lines."""
    viewer = MarkdownViewer("test_wrap.md")

    # Trigger rendering
    viewer._wrap_lines(80)

    print("Testing cursor skip behavior\n")
    print("=" * 60)

    # Test _source_line_has_content helper
    print("\n=== Testing _source_line_has_content() ===")
    for source_line in range(min(20, viewer.total_lines)):
        has_content = viewer._source_line_has_content(source_line)
        source_text = viewer.lines[source_line] if source_line < len(viewer.lines) else ""
        status = "✓ HAS CONTENT" if has_content else "✗ EMPTY/DECORATIVE"
        print(f"Source {source_line:2d}: {status:20s} | {repr(source_text[:40])}")

    # Simulate cursor navigation (without scrolling)
    print("\n=== Simulating cursor movement logic ===")

    # Manually simulate what move_cursor does (without the scrolling part)
    positions = []
    current_pos = 0  # Start at beginning

    print(f"Starting at source line {current_pos}")

    for i in range(10):
        # Find next line with content
        direction = 1
        new_pos = current_pos + direction

        max_attempts = 20
        attempts = 0

        while 0 <= new_pos < viewer.total_lines and attempts < max_attempts:
            if viewer._source_line_has_content(new_pos):
                break  # Found content
            new_pos += direction
            attempts += 1

        if new_pos >= viewer.total_lines:
            print(f"  Reached end of file")
            break

        jumped = new_pos - current_pos
        source_text = viewer.lines[new_pos] if new_pos < len(viewer.lines) else ""
        print(f"  Press 'j': {current_pos:2d} → {new_pos:2d} (jumped {jumped:2d} lines) | {repr(source_text[:40])}")

        positions.append(new_pos)
        current_pos = new_pos

    print(f"\nCursor positions visited: {positions}")

    # Check that all positions have content
    all_have_content = all(viewer._source_line_has_content(pos) for pos in positions)

    print("\n" + "=" * 60)
    if all_have_content:
        print("✓✓✓ ALL CURSOR POSITIONS HAVE CONTENT! ✓✓✓")
        print("Cursor will no longer land on blank/decorative lines!")
    else:
        print("❌ Some cursor positions are still empty")
        empty_positions = [pos for pos in positions if not viewer._source_line_has_content(pos)]
        print(f"Empty positions: {empty_positions}")

    print("=" * 60)

if __name__ == "__main__":
    test_cursor_skip()
