import argparse
import getpass
import os

from app.ingestion.bilibili_client import (
    BilibiliClient,
)
from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)


def login(
    store: BilibiliSessionStore,
) -> None:
    sessdata = os.environ.get(
        "BILIBILI_SESSDATA",
        "",
    ).strip()

    if not sessdata:
        sessdata = getpass.getpass(
            "请输入 Bilibili SESSDATA "
            "(输入不会显示): "
        ).strip()

    if not sessdata:
        raise RuntimeError(
            "SESSDATA cannot be empty"
        )

    print(
        "正在验证登录状态..."
    )

    client = BilibiliClient(
        sessdata=sessdata
    )

    if not client.is_authenticated():
        raise RuntimeError(
            "Bilibili 登录验证失败"
        )

    session = store.save(
        sessdata
    )

    print(
        "登录成功。"
    )

    print(
        "本地 Session 有效至:",
        session.expires_at.isoformat(),
    )


def status(
    store: BilibiliSessionStore,
) -> None:
    session = store.load()

    if session is None:
        print(
            "Bilibili login: guest"
        )

        return

    client = BilibiliClient(
        sessdata=session.sessdata
    )

    print(
        "正在验证 Bilibili 登录状态..."
    )

    if not client.is_authenticated():
        store.clear()

        print(
            "Bilibili login: expired"
        )

        return

    print(
        "Bilibili login: authenticated"
    )

    print(
        "Local session expires at:",
        session.expires_at.isoformat(),
    )


def logout(
    store: BilibiliSessionStore,
) -> None:
    store.clear()

    print(
        "Local Bilibili session cleared."
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "action",
        choices=[
            "login",
            "status",
            "logout",
        ],
    )

    args = parser.parse_args()

    store = (
        BilibiliSessionStore()
    )

    if args.action == "login":
        login(
            store
        )

    elif args.action == "status":
        status(
            store
        )

    elif args.action == "logout":
        logout(
            store
        )


if __name__ == "__main__":
    main()