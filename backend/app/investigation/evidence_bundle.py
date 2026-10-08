"""Query -> literal retrieval -> windows -> context -> bounded evidence.

No Archive Pipeline writes or LLM calls. Retrieval is capped independently at
20 hits per kind, before aggregation; the bundle is not an exhaustive archive.
"""

import sqlite3
from typing import Literal

from pydantic import BaseModel

from app.investigation.evidence_aggregation import aggregate_evidence_windows
from app.investigation.evidence_context import expand_evidence_window
from app.investigation.evidence_selector import (
    DEFAULT_MAX_DANMAKU,
    DEFAULT_MAX_TRANSCRIPTS,
    SelectedEvidenceWindow,
    select_window_evidence,
    validate_selection_limits,
)
from app.repository.danmaku_repo import search_danmaku_for_vtuber
from app.repository.transcript_segment_repo import search_transcripts_for_vtuber
from app.repository.vtuber_repo import get_vtuber


RETRIEVAL_LIMIT_PER_KIND = 20


class InvestigationEvidenceBundle(BaseModel):
    vtuber_id: str
    query: str
    transcript_hit_count: int
    danmaku_hit_count: int
    windows: list[SelectedEvidenceWindow]
    evidence_boundary: Literal["speech_and_audience_reaction_separate"] = (
        "speech_and_audience_reaction_separate"
    )


def build_investigation_evidence(
    connection: sqlite3.Connection,
    vtuber_id: str,
    query: str,
    max_windows: int = 8,
    *,
    max_transcripts: int = DEFAULT_MAX_TRANSCRIPTS,
    max_danmaku: int = DEFAULT_MAX_DANMAKU,
) -> InvestigationEvidenceBundle:
    """Return stored speech and viewer reactions without inferring host facts.

    Caps are per window. If a caller sets a cap below the number of seeds,
    selection fails explicitly rather than dropping seeds or exceeding that cap.
    """
    vtuber_id, query = vtuber_id.strip(), query.strip()
    if not vtuber_id:
        raise ValueError("vtuber_id cannot be empty")
    if type(max_windows) is not int or not 1 <= max_windows <= 50:
        raise ValueError("max_windows must be an integer between 1 and 50")
    validate_selection_limits(max_transcripts, max_danmaku)

    # Use one read snapshot without committing or rolling back a caller's writes.
    owns_transaction = not connection.in_transaction
    if owns_transaction:
        connection.execute("BEGIN")
    try:
        if get_vtuber(connection, vtuber_id) is None:
            raise ValueError(f"VTuber not found: {vtuber_id}")
        transcripts = search_transcripts_for_vtuber(
            connection, vtuber_id=vtuber_id, query=query, limit=RETRIEVAL_LIMIT_PER_KIND,
        )
        danmaku = search_danmaku_for_vtuber(
            connection, vtuber_id=vtuber_id, query=query, limit=RETRIEVAL_LIMIT_PER_KIND,
        )
        windows = aggregate_evidence_windows(
            transcripts, danmaku, max_windows=max_windows,
        )
        return InvestigationEvidenceBundle(
            vtuber_id=vtuber_id, query=query,
            transcript_hit_count=len(transcripts), danmaku_hit_count=len(danmaku),
            windows=[select_window_evidence(
                expand_evidence_window(connection, window, vtuber_id=vtuber_id),
                max_transcripts=max_transcripts, max_danmaku=max_danmaku,
            ) for window in windows],
        )
    finally:
        if owns_transaction:
            connection.rollback()
