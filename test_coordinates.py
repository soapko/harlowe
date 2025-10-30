#!/usr/bin/env python3
"""Test to understand coordinate system for scrolling."""

import sys
import asyncio
sys.path.insert(0, '/Users/karl/.local/pipx/venvs/harlowe/lib/python3.14/site-packages')

from textual.widgets import Static
from textual.app import App, ComposeResult
from textual.geometry import Region, Spacing

results = []

class TestViewer(Static):
    """Test viewer with line content."""

    def __init__(self):
        super().__init__()
        self.can_focus = True

    def render(self):
        lines = [f"Line {i+1:4d}" for i in range(100)]
        return "\n".join(lines)

class TestApp(App):
    """Test app to understand coordinates."""

    CSS = """
    TestViewer {
        height: 20;
        overflow-y: auto;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        self.viewer = TestViewer()
        yield self.viewer

    async def on_mount(self):
        """Test coordinate system."""
        global results
        await asyncio.sleep(0.3)

        try:
            # Log initial state
            results.append(f"Widget size: {self.viewer.size}")
            results.append(f"Scroll offset: {self.viewer.scroll_offset}")
            results.append(f"Virtual size: {self.viewer.virtual_size}")
            results.append(f"Content size: {self.viewer.content_size}")

            # Test scrolling using line number as Y coordinate
            # If lines are rendered sequentially, line 50 should be at y=50
            results.append("\n--- Testing scroll_to(y=50) ---")
            self.viewer.scroll_to(y=50, animate=False)
            await asyncio.sleep(0.2)
            results.append(f"After scroll_to(y=50), scroll_offset: {self.viewer.scroll_offset}")

            # Test scroll_to_region
            results.append("\n--- Testing scroll_to_region(Region(y=75, height=1)) ---")
            region = Region(0, 75, self.viewer.size.width, 1)
            self.viewer.scroll_to_region(region, animate=False)
            await asyncio.sleep(0.2)
            results.append(f"After scroll_to_region(y=75), scroll_offset: {self.viewer.scroll_offset}")

        except Exception as e:
            results.append(f"✗ Error: {e}")
            import traceback
            results.append(traceback.format_exc())

        self.exit()

if __name__ == "__main__":
    app = TestApp()
    app.run()

    for result in results:
        print(result)
