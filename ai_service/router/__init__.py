"""Turn router: decides what the user wants from each chat message (design §5)."""

from .rules import (
    MEMORY_FORGET,
    MEMORY_LIST,
    MEMORY_QUERY,
    MEMORY_SAVE,
    RuleMatch,
    match_memory_rule,
)

__all__ = [
    "MEMORY_FORGET",
    "MEMORY_LIST",
    "MEMORY_QUERY",
    "MEMORY_SAVE",
    "RuleMatch",
    "match_memory_rule",
]
