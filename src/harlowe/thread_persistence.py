"""Thread persistence for saving and loading comment threads."""

import json
from pathlib import Path
from typing import List, Optional
from .models import CommentThread


class ThreadPersistence:
    """
    Handles persistence of comment threads to disk.

    Threads are stored in a hidden .harlowe directory alongside
    the markdown file being edited.
    """

    def __init__(self, markdown_file_path: str, threads_dir: Optional[str] = None):
        """
        Initialize thread persistence.

        Args:
            markdown_file_path: Path to the markdown file being edited
            threads_dir: Optional custom directory for thread storage.
                        Defaults to .harlowe in the same directory as the markdown file.
        """
        self.markdown_file_path = Path(markdown_file_path)

        if threads_dir:
            self.threads_dir = Path(threads_dir)
        else:
            # Store in .harlowe directory next to markdown file
            self.threads_dir = self.markdown_file_path.parent / ".harlowe"

        # Ensure directory exists
        self.threads_dir.mkdir(parents=True, exist_ok=True)

        # Thread file name based on markdown filename
        self.threads_file = self.threads_dir / f"{self.markdown_file_path.stem}.threads.json"

    def save_threads(self, threads: List[CommentThread]) -> None:
        """
        Save all threads to disk.

        Args:
            threads: List of CommentThread objects to save
        """
        try:
            # Debug logging
            with open("/tmp/harlowe_debug.log", "a") as log:
                from datetime import datetime
                log.write(f"\n[{datetime.now()}] save_threads called\n")
                log.write(f"  threads_file: {self.threads_file}\n")
                log.write(f"  num_threads: {len(threads)}\n")
                log.write(f"  threads: {[str(t.id)[:8] for t in threads]}\n")

            data = {
                "markdown_file": str(self.markdown_file_path),
                "threads": [thread.to_dict() for thread in threads]
            }

            with open(self.threads_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Confirm write
            with open("/tmp/harlowe_debug.log", "a") as log:
                log.write(f"  SUCCESS: File written\n")

        except Exception as e:
            # Log error but don't crash the app
            import traceback
            error_msg = f"Warning: Failed to save threads: {e}\n{traceback.format_exc()}"
            print(error_msg)
            # Also write to a log file so we can debug
            try:
                with open("/tmp/harlowe_debug.log", "a") as log:
                    from datetime import datetime
                    log.write(f"\n[{datetime.now()}] ERROR: {error_msg}\n")
            except:
                pass

    def load_threads(self) -> List[CommentThread]:
        """
        Load threads from disk.

        Returns:
            List of CommentThread objects, or empty list if file doesn't exist
        """
        if not self.threads_file.exists():
            with open("/tmp/harlowe_debug.log", "a") as log:
                from datetime import datetime
                log.write(f"\n[{datetime.now()}] load_threads: File does not exist: {self.threads_file}\n")
            return []

        try:
            with open(self.threads_file, 'r') as f:
                data = json.load(f)

            # Validate that this is for the correct file
            # Compare resolved absolute paths to handle relative vs absolute paths
            stored_path_str = data.get("markdown_file", "")
            stored_path = Path(stored_path_str)

            # If stored path is relative, resolve it relative to the threads directory parent
            if not stored_path.is_absolute():
                stored_path = (self.threads_dir.parent / stored_path).resolve()
            else:
                stored_path = stored_path.resolve()

            current_path = self.markdown_file_path.resolve()

            if stored_path != current_path:
                print(f"Warning: Thread file mismatch, ignoring")
                return []

            threads = [
                CommentThread.from_dict(thread_data)
                for thread_data in data.get("threads", [])
            ]

            with open("/tmp/harlowe_debug.log", "a") as log:
                from datetime import datetime
                log.write(f"\n[{datetime.now()}] load_threads: Loaded {len(threads)} threads\n")
                for t in threads:
                    log.write(f"  Thread {str(t.id)[:8]}: {len(t.messages)} messages\n")

            return threads

        except Exception as e:
            with open("/tmp/harlowe_debug.log", "a") as log:
                from datetime import datetime
                import traceback
                log.write(f"\n[{datetime.now()}] load_threads ERROR: {e}\n{traceback.format_exc()}\n")
            print(f"Warning: Failed to load threads: {e}")
            return []

    def clear_threads(self) -> None:
        """Delete the threads file."""
        try:
            if self.threads_file.exists():
                self.threads_file.unlink()
        except Exception as e:
            print(f"Warning: Failed to clear threads: {e}")

    def auto_save(self, threads: List[CommentThread]) -> None:
        """
        Auto-save threads (debounced version for frequent updates).

        This can be called frequently; the actual file write
        happens immediately for now, but could be debounced in the future.
        """
        self.save_threads(threads)
