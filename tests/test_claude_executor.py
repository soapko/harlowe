"""Tests for Claude executor."""

import pytest
import asyncio
from harlowe.claude_executor import ClaudeExecutor, EditStatus, EditRequest


def test_add_edit_request():
    """Test adding edit requests to queue."""
    executor = ClaudeExecutor()

    request = executor.add_edit_request(
        selected_text="Hello world",
        comment="Make this more formal",
        line_start=1,
        line_end=1
    )

    assert request.id == 1
    assert request.selected_text == "Hello world"
    assert request.comment == "Make this more formal"
    assert request.status == EditStatus.PENDING
    assert len(executor.queue) == 1


def test_multiple_requests():
    """Test adding multiple edit requests."""
    executor = ClaudeExecutor()

    request1 = executor.add_edit_request("Text 1", "Edit 1", 1, 1)
    request2 = executor.add_edit_request("Text 2", "Edit 2", 2, 2)

    assert request1.id == 1
    assert request2.id == 2
    assert len(executor.queue) == 2


def test_get_pending_count():
    """Test getting pending count."""
    executor = ClaudeExecutor()

    assert executor.get_pending_count() == 0

    executor.add_edit_request("Text", "Edit", 1, 1)
    assert executor.get_pending_count() == 1


def test_build_prompt():
    """Test prompt building."""
    executor = ClaudeExecutor()

    request = EditRequest(
        id=1,
        selected_text="Original text",
        comment="Make it better",
        line_start=5,
        line_end=7
    )

    prompt = executor._build_prompt(request)

    assert "Original text" in prompt
    assert "Make it better" in prompt
    assert "lines 5-7" in prompt


def test_clear_completed():
    """Test clearing completed edits."""
    executor = ClaudeExecutor()

    request1 = executor.add_edit_request("Text 1", "Edit 1", 1, 1)
    request2 = executor.add_edit_request("Text 2", "Edit 2", 2, 2)

    # Mark one as completed
    request1.status = EditStatus.COMPLETED

    executor.clear_completed()

    assert len(executor.queue) == 1
    assert executor.queue[0].id == 2
