#!/usr/bin/env python3
"""Integration test for scrolling functionality."""

import sys
import asyncio
sys.path.insert(0, '/Users/karl/.local/pipx/venvs/harlowe/lib/python3.14/site-packages')

from textual.widgets import Static
from textual.app import App, ComposeResult

results = []

class TestScrollViewer(Static):
    """Test viewer to verify scroll_to works."""

    def __init__(self):
        super().__init__()
        self.can_focus = True

    def render(self):
        lines = [f"Line {i+1}" for i in range(100)]
        return "\n".join(lines)

class TestApp(App):
    """Test app to verify scrolling."""

    def compose(self) -> ComposeResult:
        self.viewer = TestScrollViewer()
        yield self.viewer

    async def on_mount(self):
        """Test scrolling on mount."""
        global results
        # Wait a bit for rendering
        await asyncio.sleep(0.1)

        try:
            # Test scroll_to with None for x
            self.viewer.scroll_to(x=None, y=10, animate=False)
            results.append("✓ scroll_to(x=None, y=10, animate=False) works")

            await asyncio.sleep(0.1)

            # Test scroll_to with different y values
            self.viewer.scroll_to(x=None, y=50, animate=False)
            results.append("✓ scroll_to(x=None, y=50, animate=False) works")

            results.append("\n✓ All scrolling tests passed!")

        except Exception as e:
            results.append(f"✗ Scrolling test failed: {e}")
            import traceback
            results.append(traceback.format_exc())

        # Exit the app
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run()

    # Print results after app exits
    for result in results:
        print(result)
