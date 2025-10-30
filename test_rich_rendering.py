#!/usr/bin/env python3
"""Test script for Rich markdown rendering with line mapping."""

from rich.console import Console
from rich.markdown import Markdown
import markdown_it
from io import StringIO


def render_with_mapping(markdown_text: str, width: int = 80):
    """
    Render markdown with Rich and build source-to-display line mapping.

    Returns:
        tuple: (rendered_strips, source_to_display_map, display_to_source_map)
        - rendered_strips: list of segment lists (one per display line)
        - source_to_display_map: dict[int, list[int]] - source line -> display lines
        - display_to_source_map: dict[int, int] - display line -> source line
    """
    # Parse markdown to get tokens with source mapping
    md = markdown_it.MarkdownIt()
    tokens = md.parse(markdown_text)

    # Render with Rich
    console = Console(width=width, file=StringIO(), legacy_windows=False)
    markdown_obj = Markdown(markdown_text)
    rendered_lines = list(console.render_lines(markdown_obj, console.options))

    # Build mapping by analyzing tokens
    source_to_display = {}
    display_to_source = {}

    # Track current position in rendered output
    display_idx = 0

    # Process tokens to build mapping
    # We'll track blocks (tokens with map attribute that represent source ranges)
    for token in tokens:
        if not hasattr(token, 'map') or not token.map:
            continue

        source_start, source_end = token.map

        # Determine how many display lines this token produces
        # This is heuristic-based and may need adjustment
        if token.type == 'heading_open':
            # ATX headers: 3 lines for H1 (box), 2 lines for H2-H6
            # We'll need to check the next inline token for level
            num_lines = 3 if display_idx == 0 else 2  # Rough heuristic
            # Add blank line after
            num_lines += 1
        elif token.type == 'paragraph_open':
            # Paragraphs: variable, depends on wrapping
            # Peek at the content to estimate
            # For now, count until we hit a blank line or next block
            num_lines = 1
            # Add blank line after
            num_lines += 1
        elif token.type == 'bullet_list_open':
            # Lists: one line per item
            num_lines = source_end - source_start
            # Add blank lines
            num_lines += 1
        elif token.type == 'fence':
            # Code blocks: wrapped in blank lines + actual code
            num_lines = 2 + (source_end - source_start - 2)  # -2 for fence markers
        else:
            continue  # Skip other token types

        # Map display lines to first source line in range
        for i in range(num_lines):
            if display_idx < len(rendered_lines):
                display_to_source[display_idx] = source_start
                if source_start not in source_to_display:
                    source_to_display[source_start] = []
                source_to_display[source_start].append(display_idx)
                display_idx += 1

    # Fill in any unmapped display lines (map to last source line)
    last_source = max(display_to_source.values()) if display_to_source else 0
    for i in range(len(rendered_lines)):
        if i not in display_to_source:
            display_to_source[i] = last_source

    return rendered_lines, source_to_display, display_to_source


def main():
    """Test the rendering and mapping."""
    test_markdown = """# Header 1

This is a paragraph on line 3.
It continues on line 4.

## Header 2

Another paragraph here.

- List item 1
- List item 2
- List item 3

```python
def example():
    pass
```

Final paragraph.
"""

    print("=== SOURCE MARKDOWN ===")
    for i, line in enumerate(test_markdown.splitlines()):
        print(f"{i:3d}: {line}")

    rendered_lines, src_to_disp, disp_to_src = render_with_mapping(test_markdown, width=60)

    print("\n=== RENDERED OUTPUT ===")
    for i, segments in enumerate(rendered_lines):
        text = "".join(seg.text for seg in segments)
        source_line = disp_to_src.get(i, "?")
        print(f"D{i:2d} (S{source_line}): {repr(text)}")

    print("\n=== SOURCE-TO-DISPLAY MAPPING ===")
    for src_line in sorted(src_to_disp.keys()):
        disp_lines = src_to_disp[src_line]
        print(f"Source {src_line:2d} -> Display {disp_lines}")

    print("\n=== DISPLAY-TO-SOURCE MAPPING ===")
    for disp_line in sorted(disp_to_src.keys()):
        src_line = disp_to_src[disp_line]
        print(f"Display {disp_line:2d} -> Source {src_line:2d}")


if __name__ == "__main__":
    main()
