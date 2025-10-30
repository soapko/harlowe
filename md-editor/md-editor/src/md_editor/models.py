"""Data models for Claude thread management."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4


class ThreadStatus(Enum):
    """Status of a comment thread."""
    PENDING = "pending"  # Waiting to start
    ACTIVE = "active"  # Currently open/in conversation
    COMPLETED = "completed"  # User closed the thread
    FAILED = "failed"  # Error occurred


class ThreadViewMode(Enum):
    """View modes for thread selector."""
    ACTIVE = "active"  # Show only active threads
    RECENT = "recent"  # All threads sorted by recent activity
    CLOSED = "closed"  # Show only completed threads


class MessageRole(Enum):
    """Role of a message in the conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """A single message in a thread conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class CommentThread:
    """
    Represents a Claude conversation thread for a specific text selection.

    Each thread corresponds to a user comment on selected text and maintains
    the full conversation history with Claude.
    """
    id: UUID = field(default_factory=uuid4)
    session_id: Optional[str] = None  # Claude CLI session ID
    selected_text: str = ""
    initial_comment: str = ""
    line_start: int = 0  # 1-indexed
    line_end: int = 0  # 1-indexed
    status: ThreadStatus = ThreadStatus.PENDING
    messages: List[Message] = field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_viewed_at: Optional[datetime] = None  # When user last viewed this thread
    awaiting_response: bool = False  # True when waiting for Claude to respond

    def add_message(self, role: MessageRole, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append(Message(role=role, content=content))
        self.updated_at = datetime.now()

    def mark_as_viewed(self) -> None:
        """Mark this thread as viewed by the user."""
        self.last_viewed_at = datetime.now()

    @property
    def has_unread_updates(self) -> bool:
        """Check if thread has updates since last viewed."""
        if self.last_viewed_at is None:
            # Never viewed - has unread if there are any messages
            return len(self.messages) > 0
        # Has unread if updated after last viewed
        return self.updated_at > self.last_viewed_at

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "session_id": self.session_id,
            "selected_text": self.selected_text,
            "initial_comment": self.initial_comment,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "status": self.status.value,
            "messages": [msg.to_dict() for msg in self.messages],
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_viewed_at": self.last_viewed_at.isoformat() if self.last_viewed_at else None,
            "awaiting_response": self.awaiting_response
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CommentThread":
        """Create from dictionary (JSON deserialization)."""
        last_viewed = data.get("last_viewed_at")
        return cls(
            id=UUID(data["id"]),
            session_id=data.get("session_id"),
            selected_text=data["selected_text"],
            initial_comment=data["initial_comment"],
            line_start=data["line_start"],
            line_end=data["line_end"],
            status=ThreadStatus(data["status"]),
            messages=[Message.from_dict(msg) for msg in data.get("messages", [])],
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_viewed_at=datetime.fromisoformat(last_viewed) if last_viewed else None,
            awaiting_response=data.get("awaiting_response", False)
        )
