"""Deterministic, bounded evidence selection without semantic inference."""

from collections import Counter
from typing import TypeVar
import unicodedata

from app.investigation.evidence_context import (
    AudienceReactionEvidence,
    EvidenceContext,
    SpeechEvidence,
)


DEFAULT_MAX_TRANSCRIPTS = 20
DEFAULT_MAX_DANMAKU = 40


class SelectedEvidenceWindow(EvidenceContext):
    # Counts make context truncation visible to a future consumer.
    speech_available: int
    audience_reaction_available: int


Evidence = TypeVar("Evidence", SpeechEvidence, AudienceReactionEvidence)


def validate_selection_limits(max_transcripts: int, max_danmaku: int) -> None:
    if any(type(value) is not int or not 1 <= value <= 100
           for value in (max_transcripts, max_danmaku)):
        raise ValueError("per-window evidence limits must be integers between 1 and 100")


def _local_range(item: SpeechEvidence | AudienceReactionEvidence) -> tuple[int, int]:
    if isinstance(item, SpeechEvidence):
        return item.start_ms, item.end_ms
    return item.timestamp_ms, item.timestamp_ms + 1


def _text_key(text: str) -> str:
    # Used for ranking only. Never change persisted text/raw_text in the bundle.
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _select(
    items: list[Evidence],
    *,
    seed_ids: set[str],
    anchors: list[tuple[int, int]],
    limit: int,
    rank_reactions: bool,
) -> tuple[list[Evidence], int]:
    by_id: dict[str, Evidence] = {}
    for item in items:
        previous = by_id.get(item.evidence_id)
        if previous is not None and previous != item:
            raise ValueError(f"conflicting copies of evidence: {item.evidence_id}")
        by_id[item.evidence_id] = item
    unique = list(by_id.values())
    seeds = [item for item in unique if item.evidence_id in seed_ids]
    if len(seeds) > limit:
        raise ValueError("seed evidence exceeds per-window limit; increase the limit")

    def time_key(item: Evidence):
        return (*_local_range(item), item.id)

    def proximity_key(item: Evidence):
        start, end = _local_range(item)
        distance = min(max(start - b, a - end, 0) for a, b in anchors)
        return (distance, *time_key(item))

    candidates = sorted(
        (item for item in unique if item.evidence_id not in seed_ids),
        key=proximity_key,
    )
    if rank_reactions:
        seen = Counter(_text_key(item.text) for item in seeds)
        penalties: dict[str, int] = {}
        for item in candidates:
            key = _text_key(item.text)
            # Punctuation-only and long single-character chants get a small
            # penalty. Short meaningful texts (e.g. 好 / 别唱) are not excluded.
            low_information = (
                not any(char.isalnum() for char in key)
                or (len(key) > 2 and len(set(key)) == 1)
            )
            penalties[item.evidence_id] = seen[key] + int(low_information)
            seen[key] += 1
        candidates.sort(key=lambda item: (penalties[item.evidence_id], *proximity_key(item)))

    selected = seeds + candidates[:limit - len(seeds)]
    return sorted(selected, key=time_key), len(unique)


def select_window_evidence(
    context: EvidenceContext,
    *,
    max_transcripts: int = DEFAULT_MAX_TRANSCRIPTS,
    max_danmaku: int = DEFAULT_MAX_DANMAKU,
) -> SelectedEvidenceWindow:
    """Keep every seed, then fill independent speech/reaction budgets."""
    validate_selection_limits(max_transcripts, max_danmaku)
    seed_ids = set(context.seed_evidence_ids)
    all_evidence = [*context.speech_evidence, *context.audience_reaction_evidence]
    available_ids = {item.evidence_id for item in all_evidence}
    if not seed_ids or not seed_ids <= available_ids:
        raise ValueError("context has missing seed evidence")
    anchors = [_local_range(item) for item in all_evidence if item.evidence_id in seed_ids]
    speech, speech_count = _select(
        context.speech_evidence, seed_ids=seed_ids, anchors=anchors,
        limit=max_transcripts, rank_reactions=False,
    )
    audience, audience_count = _select(
        context.audience_reaction_evidence, seed_ids=seed_ids, anchors=anchors,
        limit=max_danmaku, rank_reactions=True,
    )
    return SelectedEvidenceWindow(
        **context.model_dump(exclude={"speech_evidence", "audience_reaction_evidence"}),
        speech_evidence=speech, audience_reaction_evidence=audience,
        speech_available=speech_count, audience_reaction_available=audience_count,
    )
