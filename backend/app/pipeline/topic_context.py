import sqlite3

from app.pipeline.topic_candidate import (
    TopicCandidate,
)
from app.pipeline.reaction_context import (
    ReactionContext,
    build_reaction_context,
)
from app.repository.reaction_match_repo import (
    get_reaction_match_by_id,
)

def _format_reaction_context(
    context: ReactionContext,
) -> str:
    lines: list[str] = []

    lines.append(
        f"REACTION_MATCH_ID: "
        f"{context.reaction_match_id}"
    )

    lines.append(
        f"PART_ID: "
        f"{context.part_id}"
    )

    lines.append("")
    lines.append("[TRANSCRIPT]")

    for item in context.transcripts:
        lines.append(
            f"{item.start_ms}"
            f"-"
            f"{item.end_ms}"
            f" | "
            f"{item.text}"
        )

    lines.append("")
    lines.append("[AUDIENCE_REACTIONS]")

    for group in context.reaction_groups:
        lines.append(
            f"x{group.count} "
            f"{group.text} "
            f"["
            f"{group.first_timestamp_ms}"
            f"-"
            f"{group.last_timestamp_ms}"
            f"]"
        )

    lines.append("")
    lines.append(
        "RAW_DANMAKU_COUNT: "
        f"{context.raw_danmaku_count}"
    )

    return "\n".join(lines)



def build_topic_candidate_context(
    connection: sqlite3.Connection,
    *,
    candidate: TopicCandidate,
) -> str:
    blocks: list[str] = []

    for index, reaction_match_id in enumerate(
        candidate.reaction_match_ids,
        start=1,
    ):
        reaction_match = (
            get_reaction_match_by_id(
                connection,
                reaction_match_id,
            )
        )

        if reaction_match is None:
            raise ValueError(
                "reaction match does not exist: "
                f"{reaction_match_id}"
            )

        context = build_reaction_context(
            connection,
            reaction_match=reaction_match,
        )

        block = (
            f"=== REACTION #{index} ===\n"
            + _format_reaction_context(
                context
            )
        )

        blocks.append(block)

    return "\n\n".join(blocks)