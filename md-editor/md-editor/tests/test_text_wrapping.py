"""Test soft text wrapping in MarkdownViewer."""

from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from md_editor.markdown_viewer import MarkdownViewer


def test_text_wrapping_basic():
    """Test that long lines are wrapped correctly."""
    # Create a temporary file with long text
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Short\n")
        f.write("\n")
        f.write("This is a very long line that should definitely wrap when displayed in a narrow terminal window because it contains way too much text to fit on a single line.\n")
        temp_file = f.name

    try:
        # Create viewer
        viewer = MarkdownViewer(temp_file)

        # Trigger wrapping directly with a width
        viewer._wrap_lines(80)

        # Check that wrapped_lines has more entries than original lines
        assert len(viewer.wrapped_lines) > len(viewer.lines), \
            "Long line should be wrapped into multiple visual lines"

        # Check that line 3 (the long line) is wrapped into multiple entries
        line_3_entries = [wl for wl in viewer.wrapped_lines if wl[0] == 2]  # 0-indexed
        assert len(line_3_entries) > 1, \
            "The long line (line 3) should be wrapped into multiple entries"

        # Check that all wrapped entries reference the same original line
        for orig_idx, wrapped_text in line_3_entries:
            assert orig_idx == 2, "All wrapped portions should reference line 3"

        print(f"✓ Text wrapping test passed")
        print(f"  Original lines: {len(viewer.lines)}")
        print(f"  Wrapped lines: {len(viewer.wrapped_lines)}")
        print(f"  Line 3 wrapped into {len(line_3_entries)} visual lines")

    finally:
        Path(temp_file).unlink()


def test_text_wrapping_preserves_short_lines():
    """Test that short lines are not wrapped."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("Short\n")
        f.write("Another short\n")
        temp_file = f.name

    try:
        viewer = MarkdownViewer(temp_file)
        viewer._wrap_lines(80)

        # Short lines should not be wrapped
        assert len(viewer.wrapped_lines) == len(viewer.lines), \
            "Short lines should not be wrapped"

        print(f"✓ Short line preservation test passed")

    finally:
        Path(temp_file).unlink()


def test_text_wrapping_width_change():
    """Test that wrapped lines are recalculated on width change."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("This is a moderately long line that may or may not wrap depending on terminal width.\n")
        temp_file = f.name

    try:
        viewer = MarkdownViewer(temp_file)

        # Wrap at narrow width
        viewer._wrap_lines(50)
        narrow_count = len(viewer.wrapped_lines)

        # Wrap at wide width
        viewer._wrap_lines(120)
        wide_count = len(viewer.wrapped_lines)

        # Narrow width should produce more wrapped lines
        assert narrow_count >= wide_count, \
            "Narrower width should produce more or equal wrapped lines"

        print(f"✓ Width change test passed")
        print(f"  Narrow (50 chars): {narrow_count} lines")
        print(f"  Wide (120 chars): {wide_count} lines")

    finally:
        Path(temp_file).unlink()


if __name__ == "__main__":
    test_text_wrapping_basic()
    test_text_wrapping_preserves_short_lines()
    test_text_wrapping_width_change()
    print("\n✓ All text wrapping tests passed!")
