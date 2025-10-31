from textual.app import App
from textual.widgets import Static

class KeyTester(App):
    def compose(self):
        yield Static("Press Shift+Up or Shift+Down")
    
    def on_key(self, event):
        self.query_one(Static).update(f"Key: {event.key!r}")

if __name__ == "__main__":
    KeyTester().run()
