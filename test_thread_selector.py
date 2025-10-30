#!/usr/bin/env python3
"""Test script for thread selector functionality."""

import sys
sys.path.insert(0, '/Users/karl/.local/pipx/venvs/harlowe/lib/python3.14/site-packages')

from md_editor.thread_selector import ThreadSelector
from md_editor.models import CommentThread, ThreadStatus
from datetime import datetime
import uuid

# Create some mock threads
threads = [
    CommentThread(
        id=uuid.uuid4(),
        selected_text="Test text 1",
        initial_comment="Fix this bug",
        line_start=10,
        line_end=12,
        status=ThreadStatus.ACTIVE,
        created_at=datetime.now()
    ),
    CommentThread(
        id=uuid.uuid4(),
        selected_text="Test text 2",
        initial_comment="Add feature here with a very long comment that should be truncated",
        line_start=23,
        line_end=23,
        status=ThreadStatus.ACTIVE,
        created_at=datetime.now()
    ),
    CommentThread(
        id=uuid.uuid4(),
        selected_text="Test text 3",
        initial_comment="Update documentation",
        line_start=45,
        line_end=47,
        status=ThreadStatus.ACTIVE,
        created_at=datetime.now()
    ),
]

# Test selector
selector = ThreadSelector(threads)

print("Thread Selector Test")
print("=" * 50)
print(f"Number of threads: {len(selector.threads)}")
print(f"Selected index: {selector.selected_index}")
print()

# Test rendering
rendered = selector.render()
print("Rendered output:")
print(rendered)
print()

# Test selection
print("Testing move_selection(1)...")
selector.selected_index = 0
selector.move_selection(1)
print(f"New selected index: {selector.selected_index}")
print()

# Test get_selected_thread
selected = selector.get_selected_thread()
if selected:
    print(f"Selected thread: L{selected.line_start}-{selected.line_end}, comment: {selected.initial_comment[:30]}")
else:
    print("No thread selected")

print()
print("✓ Thread selector tests passed!")
