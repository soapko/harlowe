#!/usr/bin/env python3
"""Quick test of Rich markdown integration in MarkdownViewer."""

from md_editor.markdown_viewer import MarkdownViewer
from textual.geometry import Size

# Create a simple test
def test_rendering():
    """Test that Rich rendering produces output."""
    viewer = MarkdownViewer("test_wrap.md")

    # Trigger rendering by calling _wrap_lines directly with a width
    viewer._wrap_lines(80)

    print(f"Total source lines: {viewer.total_lines}")
    print(f"Rich rendered lines: {len(viewer.rendered_lines)}")
    print(f"Wrapped lines (for compatibility): {len(viewer.wrapped_lines)}")
    print(f"Display-to-source mapping entries: {len(viewer.display_to_source)}")

    if viewer.use_rich_rendering:
        print("\n✓ Rich rendering is ENABLED")
    else:
        print("\n✗ Rich rendering is DISABLED")

    # Show first few rendered lines
    print("\n=== First 10 rendered lines ===")
    for i in range(min(10, len(viewer.rendered_lines))):
        segments = viewer.rendered_lines[i]
        text = "".join(seg.text for seg in segments)
        source_line = viewer.display_to_source.get(i, "?")
        print(f"D{i:2d} (S{source_line:2d}): {repr(text[:60])}")

    # Test line mapping
    print("\n=== Line mapping test ===")
    for source_line in [0, 2, 4, 8]:
        if source_line < len(viewer.lines):
            # Find which display lines map to this source line
            display_lines = [d for d, s in viewer.display_to_source.items() if s == source_line]
            source_text = viewer.lines[source_line]
            print(f"Source {source_line}: {repr(source_text[:40])}")
            print(f"  → Display lines: {display_lines}")

    print("\n✓ Test completed without errors!")

if __name__ == "__main__":
    test_rendering()
