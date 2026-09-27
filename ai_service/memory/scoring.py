"""Ranking of retrieved memories (design §8).

score = 0.55·similarity + 0.20·importance + 0.15·confidence + 0.10·recency

A weighted sum, not a product, so one low factor can't sink a memory (a
birthday saved a year ago must still rank high). Recency only decays for
events and temporary facts; lasting facts keep full recency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

W_SIMILARITY = 0.55
W_IMPORTANCE = 0.20
W_CONFIDENCE = 0.15
W_RECENCY = 0.10

# Memories below this confidence never reach a prompt (design §8).
MIN_CONFIDENCE = 0.5
# Below this cosine similarity a memory isn't about the question at all.
# Tuned for gemini-embedding-001 (2026-09-27): related question/memory pairs scored
# 0.57–0.78, unrelated ones 0.45–0.553. Re-tune (8.1c eval set) when the model changes.
MIN_SIMILARITY = 0.56
MAX_IN_PROMPT = 10
RECENCY_HALF_LIFE_DAYS = 30

DECAYING_KINDS = {"event"}

T = TypeVar("T")


def recency(kind: str, age_days: float, *, temporary: bool) -> float:
    if kind not in DECAYING_KINDS and not temporary:
        return 1.0
    return math.exp(-max(age_days, 0.0) / RECENCY_HALF_LIFE_DAYS)


def score(
    *,
    similarity: float,
    importance: float,
    confidence: float,
    kind: str,
    age_days: float,
    temporary: bool = False,
) -> float:
    return (
        W_SIMILARITY * similarity
        + W_IMPORTANCE * importance
        + W_CONFIDENCE * confidence
        + W_RECENCY * recency(kind, age_days, temporary=temporary)
    )


@dataclass
class Scored(Generic[T]):
    item: T
    similarity: float
    score: float


def rank(
    items: list[tuple[T, float, float, float, str, float, bool]],
    *,
    limit: int = MAX_IN_PROMPT,
    min_similarity: Optional[float] = MIN_SIMILARITY,
) -> list[Scored[T]]:
    """Rank (item, similarity, importance, confidence, kind, age_days, temporary) tuples.

    Drops low-confidence and (when min_similarity is set) off-topic items.
    """
    kept = []
    for item, similarity, importance, confidence, kind, age_days, temporary in items:
        if confidence < MIN_CONFIDENCE:
            continue
        if min_similarity is not None and similarity < min_similarity:
            continue
        kept.append(
            Scored(
                item,
                similarity,
                score(
                    similarity=similarity,
                    importance=importance,
                    confidence=confidence,
                    kind=kind,
                    age_days=age_days,
                    temporary=temporary,
                ),
            )
        )
    kept.sort(key=lambda s: s.score, reverse=True)
    return kept[:limit]
