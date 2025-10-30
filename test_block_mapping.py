#!/usr/bin/env python3
"""Test Rich markdown integration with block-based mapping in MarkdownViewer."""

from md_editor.markdown_viewer import MarkdownViewer

def test_block_mapping():
    """Test that block-based mapping produces sequential line numbers."""
    viewer = MarkdownViewer("test_wrap.md")

    # Trigger rendering by calling _wrap_lines directly with a width
    viewer._wrap_lines(80)

    print(f"Total source lines: {viewer.total_lines}")
    print(f"Rich rendered lines: {len(viewer.rendered_lines)}")
    print(f"Display-to-source mapping entries: {len(viewer.display_to_source)}")

    if viewer.use_rich_rendering:
        print("\n✓ Rich rendering is ENABLED (block-based mapping)")
    else:
        print("\n✗ Rich rendering is DISABLED")

    # Show first few rendered lines with line numbers
    print("\n=== First 20 rendered lines with line numbers ===")
    for i in range(min(20, len(viewer.rendered_lines))):
        segments = viewer.rendered_lines[i]
        text = "".join(seg.text for seg in segments)
        source_line = viewer.display_to_source.get(i, -1)
        line_num = source_line + 1  # 1-indexed for display
        print(f"D{i:2d} → Line {line_num:3d}: {repr(text[:50])}")

    # Test line mapping - check for sequential ordering
    print("\n=== Line mapping validation ===")
    line_numbers = [viewer.display_to_source.get(i, -1) + 1
                   for i in range(min(20, len(viewer.rendered_lines)))]
    print(f"Line numbers shown: {line_numbers}")

    # Check for the bug (out of order line numbers)
    backwards_jumps = []
    large_jumps = []

    for i in range(1, len(line_numbers)):
        diff = line_numbers[i] - line_numbers[i-1]

        if diff < 0:  # Backwards jump
            backwards_jumps.append((i, line_numbers[i-1], line_numbers[i], diff))
        elif diff > 10:  # Large forward jump (like 5 → 774)
            large_jumps.append((i, line_numbers[i-1], line_numbers[i], diff))

    if backwards_jumps:
        print(f"\n❌ FOUND {len(backwards_jumps)} BACKWARDS JUMPS:")
        for idx, prev, curr, diff in backwards_jumps:
            print(f"   Position {idx}: {prev} → {curr} (diff: {diff})")
    else:
        print(f"\n✓ No backwards jumps (good!)")

    if large_jumps:
        print(f"\n⚠️  FOUND {len(large_jumps)} LARGE JUMPS:")
        for idx, prev, curr, diff in large_jumps:
            print(f"   Position {idx}: {prev} → {curr} (diff: {diff})")
    else:
        print(f"\n✓ No large jumps (excellent!)")

    # Test scroll_to_line conversion
    print("\n=== Testing scroll_to_line conversion ===")
    for source_line in [1, 5, 10]:
        if source_line <= viewer.total_lines:
            display_line = viewer._get_display_line_for_source(source_line - 1)  # Convert to 0-indexed
            print(f"Source line {source_line} → Display line {display_line}")

    # Overall verdict
    print("\n" + "="*60)
    if not backwards_jumps and not large_jumps:
        print("✓✓✓ BLOCK-BASED MAPPING WORKING PERFECTLY! ✓✓✓")
    elif not backwards_jumps:
        print("✓ Block-based mapping better (no backwards jumps)")
        print("  (Large jumps are acceptable if blocks are sparse)")
    else:
        print("❌ Block-based mapping still has issues")

    print("="*60)

if __name__ == "__main__":
    test_block_mapping()
