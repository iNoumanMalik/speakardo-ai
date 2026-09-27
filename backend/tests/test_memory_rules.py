"""Memory rules: recognised without an AI call; reminders are never captured."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_service.router.rules import match_memory_rule


@pytest.mark.parametrize(
    "message, expected",
    [
        # save
        ("Remember that my office is in Blue Area", ("memory_save", "my office is in Blue Area", None, None)),
        ("remember: I wake up at 7", ("memory_save", "I wake up at 7", None, None)),
        ("Please note that Ali is my manager", ("memory_save", "Ali is my manager", None, None)),
        ("My sister's name is Sara, remember that", ("memory_save", "My sister's name is Sara", None, None)),
        # query
        ("What's my office?", ("memory_query", "What's my office", "work_location", None)),
        ("When is Sara's birthday?", ("memory_query", "When is Sara's birthday", "birthday", "sara")),
        ("when is my mother's birthday", ("memory_query", "when is my mother's birthday", "birthday", "mother")),
        ("Where do I work?", ("memory_query", "Where do I work", "work_location", None)),
        ("What did I tell you about my dentist?", ("memory_query", "What did I tell you about my dentist", "dentist", None)),
        ("what did I tell you about Sara", ("memory_query", "what did I tell you about Sara", None, "sara")),
        # list
        ("What do you remember about me?", ("memory_list", "What do you remember about me", None, None)),
        ("show my memories", ("memory_list", "show my memories", None, None)),
        # forget
        ("Forget my office", ("memory_forget", "my office", "work_location", None)),
        ("forget Sara", ("memory_forget", "Sara", None, "sara")),
        ("forget that I work at XYZ", ("memory_forget", "I work at XYZ", None, None)),
        ("Forget everything about Sara", ("memory_forget", "Sara", None, "sara")),
        ("forget everything you know about my mother", ("memory_forget", "my mother", None, "mother")),
    ],
)
def test_memory_messages(message, expected):
    match = match_memory_rule(message)
    assert match is not None
    assert (match.intent, match.text, match.key, match.subject) == expected


@pytest.mark.parametrize(
    "message",
    [
        "Remember to call mom at 5",
        "Don't forget to buy milk tomorrow",
        "remind me to call Sara tomorrow at 5pm",
        "When is my dentist appointment?",  # a reminder question, not a memory
        "forget it",
        "Forget about it",
        "What time is it?",
        "hi",
        "",
    ],
)
def test_other_messages_are_left_alone(message):
    assert match_memory_rule(message) is None
