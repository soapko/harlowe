#!/usr/bin/env python3
"""
Test script for Rich markdown rendering with simpler block-based mapping.

Strategy: Instead of trying to predict exact line counts, we'll use a
post-render analysis approach that's more reliable.
"""

from rich.console import Console
from rich.markdown import Markdown
import markdown_it
from io import StringIO


def render_with_block_mapping(markdown_text: str, width: int = 80):
    """
    Render markdown and create block-level source mapping.

    Instead of line-by-line mapping, we create ranges:
    - Each markdown block (header, paragraph, list, code) maps to source lines
    - Display lines within a block all map to the block's first source line

    Returns:
        tuple: (rendered_lines, display_to_source_map)
    """
    source_lines = markdown_text.splitlines()

    # Parse to get block structure
    md = markdown_it.MarkdownIt()
    tokens = md.parse(markdown_text)

    # Render with Rich
    console = Console(width=width, file=StringIO(), legacy_windows=False)
    markdown_obj = Markdown(markdown_text)
    rendered_lines = list(console.render_lines(markdown_obj, console.options))

    # Extract block information from tokens
    blocks = []
    for token in tokens:
        if hasattr(token, 'map') and token.map:
            if token.type in ['heading_open', 'paragraph_open', 'bullet_list_open',
                             'ordered_list_open', 'fence', 'blockquote_open']:
                source_start, source_end = token.map
                blocks.append({
                    'type': token.type,
                    'source_start': source_start,
                    'source_end': source_end - 1,  # Make end inclusive
                    'source_text': '\n'.join(source_lines[source_start:source_end])
                })

    print(f"\nFound {len(blocks)} blocks:")
    for i, block in enumerate(blocks):
        print(f"  Block {i}: {block['type']:20s} source lines {block['source_start']}-{block['source_end']}")
        print(f"    Content: {repr(block['source_text'][:50])}")

    # Simple mapping strategy: divide rendered lines equally among blocks
    # This is a rough approximation but much more reliable than heuristics
    lines_per_block = len(rendered_lines) / len(blocks) if blocks else 1
    display_to_source = {}

    for i, block in enumerate(blocks):
        start_display = int(i * lines_per_block)
        end_display = int((i + 1) * lines_per_block) if i < len(blocks) - 1 else len(rendered_lines)

        # Map all display lines in this range to the block's first source line
        for display_idx in range(start_display, end_display):
            display_to_source[display_idx] = block['source_start']

    return rendered_lines, display_to_source, blocks


def render_with_content_matching(markdown_text: str, width: int = 80):
    """
    Alternative strategy: Match rendered content back to source by text similarity.

    For each rendered line, find the source line with most similar content.
    This is more accurate but computationally expensive.
    """
    source_lines = markdown_text.splitlines()

    # Render with Rich
    console = Console(width=width, file=StringIO(), legacy_windows=False)
    markdown_obj = Markdown(markdown_text)
    rendered_lines = list(console.render_lines(markdown_obj, console.options))

    display_to_source = {}

    # For each rendered line, extract text and try to match to source
    for display_idx, segments in enumerate(rendered_lines):
        # Extract text from segments (strip ANSI/styling)
        rendered_text = "".join(seg.text for seg in segments).strip()

        # Skip decorative lines (boxes, blank lines)
        if not rendered_text or rendered_text.startswith('┏') or rendered_text.startswith('┃') or rendered_text.startswith('┗'):
            # Map to previous line's source, or 0 if first line
            display_to_source[display_idx] = display_to_source.get(display_idx - 1, 0)
            continue

        # Find best matching source line
        best_match = 0
        best_score = 0

        for source_idx, source_text in enumerate(source_lines):
            # Simple matching: count common words
            source_words = set(source_text.lower().split())
            rendered_words = set(rendered_text.lower().split())

            if not source_words:
                continue

            common = len(source_words & rendered_words)
            score = common / len(source_words)

            if score > best_score:
                best_score = score
                best_match = source_idx

        display_to_source[display_idx] = best_match

    return rendered_lines, display_to_source


def main():
    """Test both mapping strategies."""
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

    print("\n\n" + "="*60)
    print("STRATEGY 1: Block-Based Mapping")
    print("="*60)

    rendered_lines, display_to_source, blocks = render_with_block_mapping(test_markdown, width=60)

    print(f"\n=== RENDERED OUTPUT (Block-based) ===")
    for i, segments in enumerate(rendered_lines):
        text = "".join(seg.text for seg in segments)
        source_line = display_to_source.get(i, "?")
        print(f"D{i:2d} (S{source_line:2d}): {repr(text[:50])}")

    print("\n\n" + "="*60)
    print("STRATEGY 2: Content Matching")
    print("="*60)

    rendered_lines, display_to_source_v2 = render_with_content_matching(test_markdown, width=60)

    print(f"\n=== RENDERED OUTPUT (Content matching) ===")
    for i, segments in enumerate(rendered_lines):
        text = "".join(seg.text for seg in segments)
        source_line = display_to_source_v2.get(i, "?")
        print(f"D{i:2d} (S{source_line:2d}): {repr(text[:50])}")

    print("\n\n=== COMPARISON ===")
    print("Display  | Block-based | Content-match | Match?")
    print("---------+-------------+---------------+-------")
    for i in range(len(rendered_lines)):
        s1 = display_to_source.get(i, -1)
        s2 = display_to_source_v2.get(i, -1)
        match = "✓" if s1 == s2 else "✗"
        print(f"   {i:2d}    |      {s1:2d}     |       {s2:2d}      |   {match}")


if __name__ == "__main__":
    main()
