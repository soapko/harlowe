"""Main entry point for md-editor."""

import sys
from pathlib import Path
from .app import MarkdownEditorApp


def main():
    """Main entry point."""
    # File argument is now optional
    file_path = None

    if len(sys.argv) >= 2:
        file_path = sys.argv[1]

        # Validate file exists
        if not Path(file_path).exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)

        # Validate it's a markdown file
        if not file_path.endswith(('.md', '.markdown')):
            print(f"Warning: File does not have .md or .markdown extension")

    # Run the app (file_path may be None, which will trigger file picker)
    app = MarkdownEditorApp(file_path)
    app.run()


if __name__ == "__main__":
    main()
