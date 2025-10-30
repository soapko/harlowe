#!/usr/bin/env python3
"""Test script to verify UI integration without launching full TUI."""

import sys
from pathlib import Path

# Test with the installed package
print("=" * 60)
print("Testing UI Integration")
print("=" * 60)

# Test imports
print("\n1. Testing imports...")
try:
    from md_editor.resource_file_manager import ResourceFileManager
    print("   ✓ ResourceFileManager imported")
except ImportError as e:
    print(f"   ✗ Failed to import ResourceFileManager: {e}")
    sys.exit(1)

try:
    from md_editor.resource_file_selector import ResourceFileSelector
    print("   ✓ ResourceFileSelector imported")
except ImportError as e:
    print(f"   ✗ Failed to import ResourceFileSelector: {e}")
    sys.exit(1)

try:
    from md_editor.app import MarkdownEditorApp, ResourceFileScreen
    print("   ✓ MarkdownEditorApp and ResourceFileScreen imported")
except ImportError as e:
    print(f"   ✗ Failed to import app components: {e}")
    sys.exit(1)

# Test ResourceFileManager
print("\n2. Testing ResourceFileManager...")
test_file = "/Users/karl/Documents/_Projects/harlowe/test.md"
manager = ResourceFileManager(test_file)
available = manager.get_available_markdown_files()
print(f"   ✓ Found {len(available)} markdown files")

# Test ResourceFileSelector initialization
print("\n3. Testing ResourceFileSelector initialization...")
try:
    selector = ResourceFileSelector(
        available_files=available,
        initially_selected=[]
    )
    print(f"   ✓ ResourceFileSelector initialized with {len(available)} files")
except Exception as e:
    print(f"   ✗ Failed to initialize ResourceFileSelector: {e}")
    sys.exit(1)

# Test checkbox state management
print("\n4. Testing checkbox state management...")
if len(available) >= 2:
    # Set initial selection
    initial = [str(available[0].absolute())]
    selector2 = ResourceFileSelector(
        available_files=available,
        initially_selected=initial
    )
    print(f"   ✓ Selector initialized with 1 pre-selected file")
    print(f"   Selected: {len(selector2.checked_files)} files")

# Test app initialization with resource manager
print("\n5. Testing app initialization...")
try:
    app = MarkdownEditorApp(test_file)
    print(f"   ✓ MarkdownEditorApp initialized")
    print(f"   ✓ resource_manager: {type(app.resource_manager).__name__}")
    print(f"   ✓ Thread manager resource_files: {len(app.thread_manager.resource_files)} files")
except Exception as e:
    print(f"   ✗ Failed to initialize app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Check if action exists
print("\n6. Checking action_select_resources method...")
if hasattr(app, 'action_select_resources'):
    print(f"   ✓ action_select_resources method exists")
else:
    print(f"   ✗ action_select_resources method NOT FOUND")
    sys.exit(1)

# Check keybinding
print("\n7. Checking Ctrl+P keybinding...")
ctrl_p_found = False
for binding in app.BINDINGS:
    if binding.key == "ctrl+p":
        ctrl_p_found = True
        print(f"   ✓ Found binding: ctrl+p -> {binding.action}")
        break
if not ctrl_p_found:
    print(f"   ✗ Ctrl+P binding NOT FOUND")
    sys.exit(1)

print("\n" + "=" * 60)
print("All UI integration tests passed!")
print("=" * 60)
print("\nThe feature is ready for interactive testing.")
print("Run: harlowe test.md")
print("Then press Ctrl+P to open the resource file selector.")
