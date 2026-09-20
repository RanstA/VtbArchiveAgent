import sqlite3

from app.domain.danmaku import (
    Danmaku,
)
from app.ingestion.source import (
    ArchiveBundle,
)
from app.repository.danmaku_repo import (
    insert_danmaku_batch,
)
from app.repository.stream_part_repo import (
    delete_stream_parts,
    insert_stream_part,
)
from app.repository.stream_repo import (
    insert_stream,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
    insert_vtuber_source,
)


def _validate_archive_bundle(
    bundle: ArchiveBundle,
) -> None:
    """
    在开始数据库事务之前，
    检查 ArchiveBundle 内部引用是否一致。

    这里检查的是 Domain contract，
    而不是数据库约束。
    """

    if (
        bundle.stream.vtuber_id
        != bundle.vtuber.id
    ):
        raise ValueError(
            "bundle.stream.vtuber_id "
            "must match bundle.vtuber.id"
        )

    if not bundle.vtuber_sources:
        raise ValueError(
            "bundle must contain at least "
            "one vtuber source"
        )

    source_found = False

    for vtuber_source in (
        bundle.vtuber_sources
    ):
        if (
            vtuber_source.vtuber_id
            != bundle.vtuber.id
        ):
            raise ValueError(
                "all vtuber sources must "
                "belong to bundle.vtuber"
            )

        if (
            vtuber_source.source
            == bundle.source
        ):
            source_found = True

    if not source_found:
        raise ValueError(
            "bundle.source must be represented "
            "in bundle.vtuber_sources"
        )

    part_ids: set[str] = set()

    for part in bundle.parts:
        if (
            part.stream_id
            != bundle.stream.id
        ):
            raise ValueError(
                "all stream parts must belong "
                "to bundle.stream"
            )

        if (
            part.part_id
            in part_ids
        ):
            raise ValueError(
                "duplicate part_id in bundle: "
                f"{part.part_id}"
            )

        part_ids.add(
            part.part_id
        )

    for danmaku in bundle.danmaku:
        if (
            danmaku.stream_id
            != bundle.stream.id
        ):
            raise ValueError(
                "all danmaku must belong "
                "to bundle.stream"
            )

        if (
            danmaku.part_id
            not in part_ids
        ):
            raise ValueError(
                "danmaku references unknown "
                "part_id: "
                f"{danmaku.part_id}"
            )


def _group_danmaku_by_part(
    bundle: ArchiveBundle,
) -> dict[
    str,
    list[Danmaku],
]:
    result: dict[
        str,
        list[Danmaku],
    ] = {
        part.part_id: []
        for part
        in bundle.parts
    }

    for item in bundle.danmaku:
        result[
            item.part_id
        ].append(
            item
        )

    return result


def persist_archive_bundle(
    connection: sqlite3.Connection,
    bundle: ArchiveBundle,
) -> None:
    """
    将一个 ArchiveBundle 原子写入 SQLite。

    事务边界：

        Vtuber
        + VtuberSource
        + Stream
        + StreamPart
        + Danmaku

    任意一步失败时，
    整个 Bundle 的数据库修改都会 rollback。

    完整 Bundle（parts 非空）：
        替换当前 Stream 的 Part / Danmaku。

    metadata-only Bundle（parts 为空）：
        仅更新 Vtuber / Source / Stream 元数据，
        不删除已有 Part / Danmaku。

    注意：

    删除旧 StreamPart 时，
    SQLite FK ON DELETE CASCADE 会同时删除：

        Danmaku
        Highlight

    因为 Highlight 是基于旧弹幕计算出来的派生数据，
    数据重新导入后应重新检测。
    """

    _validate_archive_bundle(
        bundle
    )

    if connection.in_transaction:
        raise RuntimeError(
            "persist_archive_bundle requires "
            "a connection without an active "
            "transaction"
        )

    danmaku_by_part = (
        _group_danmaku_by_part(
            bundle
        )
    )

    with connection:
        insert_vtuber(
            connection=connection,
            vtuber=bundle.vtuber,
        )

        for vtuber_source in (
            bundle.vtuber_sources
        ):
            insert_vtuber_source(
                connection=connection,
                vtuber_source=(
                    vtuber_source
                ),
            )

        insert_stream(
            connection=connection,
            stream=bundle.stream,
        )

        # metadata-only Bundle：
        #
        # 只同步上面的元数据。
        #
        # 不允许一个“当前没有本地文件”
        # 的 Source 意外清掉数据库里
        # 已经存在的完整弹幕。
        if not bundle.parts:
            return

        # 完整重新导入：
        #
        # 删除旧 Parts。
        #
        # Danmaku / Highlight 会通过
        # FK cascade 自动失效。
        delete_stream_parts(
            connection=connection,
            stream_id=(
                bundle.stream.id
            ),
        )

        for part in bundle.parts:
            stream_part_id = (
                insert_stream_part(
                    connection=connection,
                    part=part,
                )
            )

            insert_danmaku_batch(
                connection=connection,
                stream_part_id=(
                    stream_part_id
                ),
                danmaku=(
                    danmaku_by_part[
                        part.part_id
                    ]
                ),
            )