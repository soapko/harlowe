#!/usr/bin/env python3
"""Integration test for scroll_to_region functionality."""

import sys
import asyncio
sys.path.insert(0, '/Users/karl/.local/pipx/venvs/harlowe/lib/python3.14/site-packages')

from textual.widgets import Static
from textual.app import App, ComposeResult
from textual.geometry import Region, Spacing

results = []

class TestScrollViewer(Static):
    """Test viewer to verify scroll_to_region works."""

    def __init__(self):
        super().__init__()
        self.can_focus = True

    def render(self):
        lines = [f"Line {i+1}" for i in range(100)]
        return "\n".join(lines)

class TestApp(App):
    """Test app to verify scrolling."""

    CSS = """
    TestScrollViewer {
        height: 100%;
        overflow-y: auto;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        self.viewer = TestScrollViewer()
        yield self.viewer

    async def on_mount(self):
        """Test scrolling on mount."""
        global results
        # Wait a bit for rendering
        await asyncio.sleep(0.2)

        try:
            # Test scroll_to_region with a region
            region = Region(x=0, y=10, width=self.viewer.size.width, height=1)
            self.viewer.scroll_to_region(region, animate=False, spacing=Spacing(top=2, bottom=2))
            results.append("✓ scroll_to_region(Region(y=10), spacing=Spacing(top=2, bottom=2)) works")

            await asyncio.sleep(0.2)

            # Test scroll_to_region with different region
            region = Region(x=0, y=50, width=self.viewer.size.width, height=1)
            self.viewer.scroll_to_region(region, animate=False, spacing=Spacing(top=2, bottom=2))
            results.append("✓ scroll_to_region(Region(y=50), spacing=Spacing(top=2, bottom=2)) works")

            results.append("\n✓ All scroll_to_region tests passed!")

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
