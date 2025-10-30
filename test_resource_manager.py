#!/usr/bin/env python3
"""Test script for resource file manager functionality."""

import sys
import json
from pathlib import Path

# Add the source directory to path
sys.path.insert(0, str(Path(__file__).parent / "md-editor/md-editor/src"))

from md_editor.resource_file_manager import ResourceFileManager


def test_resource_manager():
    """Test the ResourceFileManager functionality."""
    print("=" * 60)
    print("Testing ResourceFileManager")
    print("=" * 60)

    test_file = Path("/Users/karl/Documents/_Projects/harlowe/test.md")

    # Initialize manager
    print(f"\n1. Initializing ResourceFileManager for: {test_file.name}")
    manager = ResourceFileManager(str(test_file))

    # Get available files
    print("\n2. Getting available markdown files:")
    available = manager.get_available_markdown_files()
    for f in available:
        print(f"   - {f.name}")

    # Get current resources (should be empty initially)
    print("\n3. Getting current resources:")
    current = manager.get_resources()
    print(f"   Current resources: {current if current else 'None'}")

    # Set some resources
    print("\n4. Setting test resources:")
    if len(available) >= 2:
        test_resources = [str(available[0].absolute()), str(available[1].absolute())]
        print(f"   Selecting: {[Path(r).name for r in test_resources]}")
        manager.set_resources(test_resources)
    else:
        print("   Not enough files to test (need at least 2)")
        return

    # Verify persistence
    print("\n5. Verifying persistence:")
    json_file = manager.resource_file_path
    print(f"   Checking file: {json_file}")
    if json_file.exists():
        with open(json_file, 'r') as f:
            data = json.load(f)
        print(f"   Saved data: {json.dumps(data, indent=2)}")

    # Create new manager instance to test loading
    print("\n6. Testing load with new manager instance:")
    manager2 = ResourceFileManager(str(test_file))
    loaded = manager2.get_resources()
    print(f"   Loaded resources: {[Path(r).name for r in loaded]}")

    # Clear resources
    print("\n7. Clearing resources:")
    manager2.set_resources([])
    cleared = manager2.get_resources()
    print(f"   Resources after clear: {cleared if cleared else 'Empty'}")

    # Check that entry was removed from JSON
    if json_file.exists():
        with open(json_file, 'r') as f:
            data = json.load(f)
        print(f"   JSON after clear: {json.dumps(data, indent=2) if data else '{}'}")

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    test_resource_manager()
